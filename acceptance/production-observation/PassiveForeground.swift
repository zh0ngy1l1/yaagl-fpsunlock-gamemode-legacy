// Acceptance-only host observer. Never starts or signals the product.
// Reuses the repaired observer's prohibited AppKit policy and NSWorkspace
// notifications, with no Carbon keys, preflight commands or process-memory API.
import Foundation
import AppKit
import Darwin

struct Invalid: Error, CustomStringConvertible { let description: String }
func check(_ ok: Bool, _ message: String) throws {
    if !ok { throw Invalid(description: message) }
}
struct Identity: Codable, Equatable {
    let pid: Int32
    let executable: String
    let launchDate: String
    let name: String
    var complete: Bool { pid > 0 && !executable.isEmpty && !launchDate.isEmpty }
    func sameProcess(_ other: Identity) -> Bool {
        pid == other.pid && executable == other.executable && launchDate == other.launchDate
    }
}
func utc(_ date: Date = Date()) -> String {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return f.string(from: date)
}
func identity(_ app: NSRunningApplication?) -> Identity? {
    guard let app else { return nil }
    return Identity(pid: app.processIdentifier,
        executable: app.executableURL?.resolvingSymlinksInPath().path ?? "",
        // Round-trip the supplied Date's Double precision; do not truncate birth
        // identity to the millisecond precision of the human UTC event display.
        launchDate: app.launchDate.map { String(format: "%.17g", $0.timeIntervalSinceReferenceDate) } ?? "",
        name: app.localizedName ?? "")
}
func dictionary(_ value: Identity?) -> Any {
    guard let value else { return NSNull() }
    return ["pid": value.pid, "executable": value.executable,
            "launchDate": value.launchDate, "name": value.name] as [String: Any]
}

// Pure reducer: callbacks and heartbeat snapshots are inputs. It cannot prove
// delivery of every OS notification. It detects stale callbacks, identity reuse,
// foreground disagreement and long observation gaps; video is independent evidence.
final class Model {
    let expectedPath: String
    let observerPID: Int32
    var bound: Identity?
    var selectedHosts: [Identity] = []
    var departed = false
    var terminated = false
    var focused = false
    var failures: [String] = []
    var lastHeartbeat: UInt64?
    var lastTime: UInt64 = 0
    init(path: String, observerPID: Int32) {
        expectedPath = path; self.observerPID = observerPID
    }
    func fail(_ message: String) {
        if !failures.contains(message) { failures.append(message) }
    }
    func receive(_ kind: String, affected: Identity?, front: Identity?, now: UInt64) {
        if now < lastTime { fail("monotonic_clock_reversed") }
        lastTime = max(now, lastTime)
        if front?.pid == observerPID { fail("observer_became_foreground") }
        for item in [affected, front].compactMap({ $0 }) where item.executable == expectedPath {
            if !item.complete { fail("selected_host_identity_incomplete"); continue }
            if !selectedHosts.contains(where: { $0.sameProcess(item) }) {
                selectedHosts.append(item)
            }
            if selectedHosts.count > 1 { fail("multiple_selected_hosts") }
        }
        if let bound, let affected, affected.pid == bound.pid,
           !affected.sameProcess(bound) { fail("bound_pid_identity_changed") }
        if kind == "startup" && selectedHosts.count > 0 { fail("selected_host_already_running") }
        if let bound, focused && !terminated {
            let selectedTerminal = (kind == "deactivate" || kind == "terminate") &&
                (affected.map { $0.sameProcess(bound) } ?? false)
            if !selectedTerminal {
                // Every delivered event supplies evidence, not only heartbeats.
                // A short excursion may fit between heartbeat samples while its
                // other-app activation still proves the continuous span was lost.
                if kind == "activate", let affected, !affected.sameProcess(bound) {
                    fail("other_application_activated_during_selected_span")
                }
                if !(front.map { $0.sameProcess(bound) } ?? false) {
                    fail("foreground_event_snapshot_disagreement")
                }
            }
        }
        if kind == "activate", let affected, affected.executable == expectedPath {
            if !affected.complete { fail("selected_host_identity_incomplete") }
            else if bound == nil { bound = affected }
            if departed || terminated { fail("reactivation_after_departure") }
            focused = true
        }
        if kind == "deactivate", let bound, let affected, affected.sameProcess(bound) {
            departed = true; focused = false
        }
        if kind == "terminate", let bound, let affected, affected.sameProcess(bound) {
            terminated = true; focused = false
        }
        if kind == "heartbeat" {
            if let lastHeartbeat, now < lastHeartbeat || now - lastHeartbeat > 3_000_000_000 {
                fail("heartbeat_gap_over_3_seconds")
            }
            lastHeartbeat = now
            if let bound, !terminated {
                let seenFocused = front.map { $0.sameProcess(bound) } ?? false
                if seenFocused != focused { fail("foreground_notification_snapshot_disagreement") }
            } else if bound == nil && front?.executable == expectedPath {
                fail("selected_foreground_without_activation_notification")
            }
        }
    }
    var summary: [String: Any] {
        ["bound": dictionary(bound), "departed": departed, "terminated": terminated,
         "failures": failures, "selected_host_count": selectedHosts.count,
         "integrity_ok": failures.isEmpty,
         "complete_native_lifecycle": bound != nil && terminated,
         "event_delivery_completeness": "not provable; no detected loss is weaker than guaranteed delivery",
         "windows_pid_mapping": "not established by this native observer"]
    }
}

final class Journal {
    let handle: FileHandle
    var sequence = 0
    init(_ path: String) throws {
        let fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
        try check(fd >= 0, "Journal exists or cannot be exclusively created")
        handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
    }
    func emit(_ kind: String, now: UInt64, values: [String: Any]) throws {
        try check(sequence < 20000, "Journal bound exhausted")
        sequence += 1
        var row = values
        row["kind"] = kind; row["sequence"] = sequence
        row["monotonic_ns"] = now; row["utc"] = utc()
        var bytes = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
        bytes.append(10)
        try handle.write(contentsOf: bytes)
        // Host-only, once per event. Never changes the production polling loop.
        try handle.synchronize()
    }
}

func selfTest() throws {
    let wine = Identity(pid: 10, executable: "/selected/wine", launchDate: "date1", name: "game")
    let other = Identity(pid: 20, executable: "/other", launchDate: "date2", name: "other")
    var count = 0
    func tested(_ ok: Bool, _ name: String) throws { try check(ok, name); count += 1 }
    func model() -> Model { Model(path: wine.executable, observerPID: 99) }
    let normal = model()
    normal.receive("startup", affected: nil, front: other, now: 1)
    normal.receive("activate", affected: wine, front: wine, now: 2)
    normal.receive("heartbeat", affected: nil, front: wine, now: 1_000_000_000)
    normal.receive("deactivate", affected: wine, front: other, now: 2_000_000_000)
    normal.receive("terminate", affected: wine, front: other, now: 2_100_000_000)
    normal.receive("heartbeat", affected: nil, front: other, now: 3_000_000_000)
    try tested(normal.failures.isEmpty && normal.terminated && normal.departed, "normal terminal departure")
    normal.receive("activate", affected: wine, front: wine, now: 4_000_000_000)
    try tested(normal.failures.contains("reactivation_after_departure"), "reject renewed focus")
    let missed = model()
    missed.receive("heartbeat", affected: nil, front: wine, now: 1)
    try tested(missed.failures.contains("selected_foreground_without_activation_notification"), "missed initial activation")
    let lost = model()
    lost.receive("activate", affected: wine, front: wine, now: 1)
    lost.receive("heartbeat", affected: nil, front: other, now: 2)
    try tested(lost.failures.contains("foreground_notification_snapshot_disagreement"), "missing departure")
    let gap = model()
    gap.receive("heartbeat", affected: nil, front: other, now: 1)
    gap.receive("heartbeat", affected: nil, front: other, now: 3_000_000_002)
    try tested(gap.failures.contains("heartbeat_gap_over_3_seconds"), "heartbeat gap")
    gap.receive("heartbeat", affected: nil, front: other, now: 0)
    try tested(gap.failures.contains("monotonic_clock_reversed"), "backward clock")
    let reuse = model()
    reuse.receive("activate", affected: wine, front: wine, now: 1)
    let replacement = Identity(pid: 10, executable: wine.executable, launchDate: "date3", name: "game")
    reuse.receive("launch", affected: replacement, front: replacement, now: 2)
    try tested(reuse.failures.contains("bound_pid_identity_changed") && reuse.failures.contains("multiple_selected_hosts"), "PID reuse")
    let bad = model()
    bad.receive("activate", affected: Identity(pid: 10, executable: wine.executable, launchDate: "", name: "game"), front: nil, now: 1)
    try tested(bad.failures.contains("selected_host_identity_incomplete") && bad.bound == nil, "missing birth identity")
    let early = model()
    early.receive("startup", affected: wine, front: wine, now: 1)
    try tested(early.failures.contains("selected_host_already_running"), "observer started too late")
    let selfFocus = model()
    selfFocus.receive("heartbeat", affected: nil, front: Identity(pid: 99, executable: "/observer", launchDate: "date", name: "observer"), now: 1)
    try tested(selfFocus.failures.contains("observer_became_foreground"), "observer must not steal focus")
    let excursion = model()
    excursion.receive("activate", affected: wine, front: wine, now: 1)
    excursion.receive("activate", affected: other, front: other, now: 2)
    excursion.receive("heartbeat", affected: nil, front: wine, now: 3)
    try tested(excursion.failures.contains("other_application_activated_during_selected_span") &&
               excursion.failures.contains("foreground_event_snapshot_disagreement"),
               "recorded short excursion survives matching later heartbeat")
    let contradictoryActivation = model()
    contradictoryActivation.receive("activate", affected: wine, front: wine, now: 1)
    contradictoryActivation.receive("activate", affected: other, front: wine, now: 2)
    try tested(contradictoryActivation.failures.contains("other_application_activated_during_selected_span"),
               "other-app activation cannot be hidden by a matching current snapshot")
    let nonHeartbeat = model()
    nonHeartbeat.receive("activate", affected: wine, front: wine, now: 1)
    nonHeartbeat.receive("launch", affected: other, front: other, now: 2)
    try tested(nonHeartbeat.failures.contains("foreground_event_snapshot_disagreement"),
               "non-heartbeat foreground loss is evidence")
    print("{\"suite\":\"passive-foreground-pure-model\",\"checks\":\(count),\"failures\":0,\"native_observation_executed\":false}")
}

func observe(_ output: String, _ expected: String, _ seconds: Double, _ stopFile: String) throws {
    try check(Thread.isMainThread, "Requires main thread")
    try check(expected.hasPrefix("/") && (60...7200).contains(seconds), "Bad path or duration")
    let canonical = URL(fileURLWithPath: expected).resolvingSymlinksInPath().path
    try check(canonical == expected, "Expected executable must use canonical path")
    try check(stopFile.hasPrefix("/") && !FileManager.default.fileExists(atPath: stopFile),
              "Stop request must be a fresh absolute staging path")
    let journal = try Journal(output)
    let model = Model(path: expected, observerPID: getpid())
    let center = NSWorkspace.shared.notificationCenter
    var tokens: [NSObjectProtocol] = []
    var failed = false
    func record(_ kind: String, _ affected: NSRunningApplication? = nil) {
        let now = DispatchTime.now().uptimeNanoseconds
        let front = identity(NSWorkspace.shared.frontmostApplication)
        let who = identity(affected)
        model.receive(kind, affected: who, front: front, now: now)
        do {
            try journal.emit(kind, now: now, values: ["affected": dictionary(who), "foreground": dictionary(front),
                "expected_native_executable": expected, "observer_pid": getpid(), "state": model.summary])
        } catch { failed = true; CFRunLoopStop(CFRunLoopGetMain()) }
    }
    // Register before initializing NSApplication so any observer activation is retained.
    for (name, kind) in [(NSWorkspace.didLaunchApplicationNotification, "launch"),
                         (NSWorkspace.didActivateApplicationNotification, "activate"),
                         (NSWorkspace.didDeactivateApplicationNotification, "deactivate"),
                         (NSWorkspace.didTerminateApplicationNotification, "terminate")] {
        tokens.append(center.addObserver(forName: name, object: nil, queue: .main) { note in
            record(kind, note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication)
        })
    }
    let app = NSApplication.shared
    try check(app.setActivationPolicy(.prohibited), "Cannot prohibit activation")
    try check(app.activationPolicy() == .prohibited && app.windows.isEmpty && !app.isActive,
              "Observer is not passive")
    record("startup")
    for app in NSWorkspace.shared.runningApplications where identity(app)?.executable == expected {
        record("startup", app)
    }
    try check(model.failures.isEmpty, "A selected host already exists or observer became active")
    record("ready")
    let timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in record("heartbeat") }
    let deadline = DispatchTime.now().uptimeNanoseconds + UInt64(seconds * 1_000_000_000)
    var controllerStopped = false
    // Duration is an observation bound, never a launch or write eligibility delay.
    while DispatchTime.now().uptimeNanoseconds < deadline && !failed {
        if FileManager.default.fileExists(atPath: stopFile) {
            // A host controller ends only this observer after launcher quit.
            // Product processes are never signaled; the stop file is retained.
            let fd = open(stopFile, O_RDONLY | O_NOFOLLOW)
            try check(fd >= 0, "Stop request is not a readable regular file")
            let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
            var info = stat()
            try check(fstat(fd, &info) == 0 && (info.st_mode & S_IFMT) == S_IFREG && info.st_size == 5,
                      "Invalid stop request")
            try check(try handle.readToEnd() == Data("stop\n".utf8), "Invalid stop request content")
            controllerStopped = true
            break
        }
        RunLoop.main.run(until: Date().addingTimeInterval(0.25))
    }
    timer.invalidate()
    for token in tokens { center.removeObserver(token) }
    try check(!failed, "Journal write failed; no valid footer")
    try journal.emit("footer", now: DispatchTime.now().uptimeNanoseconds,
        values: ["state": model.summary, "event_count_before_footer": journal.sequence,
                 "expected_native_executable": expected, "observer_pid": getpid(),
                 "completion": controllerStopped ? "controller-stop-request" : "duration-bound-observer-close",
                 "production_processes_signaled": false])
}

do {
    let args = CommandLine.arguments
    if args.count == 2 && args[1] == "--self-test" { try selfTest() }
    else if args.count == 6 && args[1] == "--observe", let seconds = Double(args[4]) {
        try observe(args[2], args[3], seconds, args[5])
    } else { throw Invalid(description: "Usage: PassiveForeground --self-test | --observe OUTPUT EXACT_NATIVE_WINE_EXECUTABLE MAX_SECONDS STOP_FILE") }
} catch {
    FileHandle.standardError.write(Data((String(describing: error) + "\n").utf8))
    exit(1)
}
