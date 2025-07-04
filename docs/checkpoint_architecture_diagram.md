# Checkpoint System Architecture Diagram

## System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Claude Orchestrator Checkpoint System                                           │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                      Enhanced Orchestrator Layer                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │  │
│  │  │   Task Master   │  │   Validator     │  │   Decomposer    │  │   Optimizer     │  │   Tracer        │  │  │
│  │  │                 │  │                 │  │                 │  │                 │  │                 │  │  │
│  │  │ • Task Queue    │  │ • Validation    │  │ • Task Split    │  │ • Evaluation    │  │ • Trace Events  │  │  │
│  │  │ • Dependencies  │  │ • Reports       │  │ • Subtasks      │  │ • Optimization  │  │ • Analytics     │  │  │
│  │  │ • Status        │  │ • Compliance    │  │ • Hierarchy     │  │ • Cycles        │  │ • Monitoring    │  │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  │  │
│  │                 │                 │                 │                 │                 │                 │  │
│  │                 └─────────────────┼─────────────────┼─────────────────┼─────────────────┘                 │  │
│  │                                   │                 │                 │                                   │  │
│  └───────────────────────────────────┼─────────────────┼─────────────────┼───────────────────────────────────┘  │
│                                      │                 │                 │                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                    Checkpoint System Core                                                     │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐                     │  │
│  │  │   Checkpoint    │◄────────────►│   Checkpoint    │◄────────────►│   Checkpoint    │                     │  │
│  │  │    Manager      │              │     Data        │              │    Storage      │                     │  │
│  │  │                 │              │                 │              │                 │                     │  │
│  │  │ • Create        │              │ • State         │              │ • Persistence   │                     │  │
│  │  │ • Update        │              │ • Metadata      │              │ • Recovery      │                     │  │
│  │  │ • Complete      │              │ • Timeline      │              │ • Indexing      │                     │  │
│  │  │ • Restore       │              │ • Hierarchy     │              │ • Cleanup       │                     │  │
│  │  │ • Query         │              │ • Validation    │              │ • Compression   │                     │  │
│  │  └─────────────────┘              └─────────────────┘              └─────────────────┘                     │  │
│  │           │                                │                                │                               │  │
│  │           │                                │                                │                               │  │
│  │           ▼                                ▼                                ▼                               │  │
│  │  ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐                     │  │
│  │  │    Task         │              │    Event        │              │    Recovery     │                     │  │
│  │  │   Wrapper       │              │    System       │              │    Manager      │                     │  │
│  │  │                 │              │                 │              │                 │                     │  │
│  │  │ • Auto-track    │              │ • Notifications │              │ • Strategies    │                     │  │
│  │  │ • Progress      │              │ • State Changes │              │ • Retry Logic   │                     │  │
│  │  │ • Context       │              │ • Integration   │              │ • Failure Hand. │                     │  │
│  │  │ • Completion    │              │ • Monitoring    │              │ • Reconstruction│                     │  │
│  │  └─────────────────┘              └─────────────────┘              └─────────────────┘                     │  │
│  │                                                                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                     │                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                      Worker Integration Layer                                                │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │  │
│  │  │   Opus Manager  │  │ Sonnet Worker 1 │  │ Sonnet Worker 2 │  │ Sonnet Worker 3 │  │ Circuit Breaker │  │  │
│  │  │                 │  │                 │  │                 │  │                 │  │                 │  │  │
│  │  │ • Planning      │  │ • Code Gen      │  │ • Testing       │  │ • Documentation │  │ • Failure Det.  │  │  │
│  │  │ • Review        │  │ • Refactoring   │  │ • Debugging     │  │ • Analysis      │  │ • Auto Recovery │  │  │
│  │  │ • Orchestration │  │ • File Ops      │  │ • Validation    │  │ • Optimization  │  │ • State Monitor │  │  │
│  │  │ • Checkpointing │  │ • Checkpointing │  │ • Checkpointing │  │ • Checkpointing │  │ • Checkpointing │  │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  │  │
│  │           │                     │                     │                     │                     │          │  │
│  │           └─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┘          │  │
│  │                                 │                     │                     │                                │  │
│  └─────────────────────────────────┼─────────────────────┼─────────────────────┼────────────────────────────────┘  │
│                                    │                     │                     │                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                      Storage & Persistence Layer                                             │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐                     │  │
│  │  │   File System   │              │     Index       │              │    Backup       │                     │  │
│  │  │    Storage      │              │   Management    │              │   & Archive     │                     │  │
│  │  │                 │              │                 │              │                 │                     │  │
│  │  │ • JSON Files    │              │ • Task Index    │              │ • Periodic      │                     │  │
│  │  │ • Compression   │              │ • Worker Index  │              │ • Retention     │                     │  │
│  │  │ • Partitioning  │              │ • State Index   │              │ • Migration     │                     │  │
│  │  │ • Encryption    │              │ • Time Index    │              │ • Disaster Rec. │                     │  │
│  │  └─────────────────┘              └─────────────────┘              └─────────────────┘                     │  │
│  │                                                                                                               │  │
│  │  .taskmaster/checkpoints/                                                                                    │  │
│  │  ├── active/                                                                                                 │  │
│  │  │   ├── checkpoint_cp_task1_1_1672531200.json                                                             │  │
│  │  │   └── checkpoint_cp_task2_1_1672531260.json                                                             │  │
│  │  ├── completed/                                                                                             │  │
│  │  │   └── checkpoint_cp_task1_2_1672531320.json                                                             │  │
│  │  ├── failed/                                                                                                │  │
│  │  │   └── checkpoint_cp_task3_1_1672531380.json                                                             │  │
│  │  └── index.json                                                                                             │  │
│  │                                                                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      Checkpoint Data Flow                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                     │
│  Task Start                                                                                                         │
│      │                                                                                                              │
│      ▼                                                                                                              │
│  ┌─────────────────┐                                                                                               │
│  │   Create Task   │                                                                                               │
│  │   Context       │                                                                                               │
│  │                 │                                                                                               │
│  │ • Task ID       │                                                                                               │
│  │ • Title         │                                                                                               │
│  │ • Description   │                                                                                               │
│  │ • Worker Info   │                                                                                               │
│  └─────────────────┘                                                                                               │
│          │                                                                                                          │
│          ▼                                                                                                          │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   Checkpoint    │───▶│   Checkpoint    │───▶│   Checkpoint    │───▶│   Checkpoint    │                       │
│  │   Creation      │    │   Validation    │    │   Storage       │    │   Indexing      │                       │
│  │                 │    │                 │    │                 │    │                 │                       │
│  │ • Generate ID   │    │ • Data Valid.   │    │ • File Write    │    │ • Update Index  │                       │
│  │ • Initialize    │    │ • Schema Check  │    │ • Compression   │    │ • Task Map      │                       │
│  │ • Set State     │    │ • Integrity     │    │ • Encryption    │    │ • Worker Map    │                       │
│  │ • Metadata      │    │ • Constraints   │    │ • Persistence   │    │ • State Map     │                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│          │                       │                       │                       │                                │
│          │                       │                       │                       │                                │
│          ▼                       ▼                       ▼                       ▼                                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   Event         │    │   Memory        │    │   File System   │    │   Index         │                       │
│  │   Emission      │    │   Cache         │    │   Storage       │    │   Update        │                       │
│  │                 │    │                 │    │                 │    │                 │                       │
│  │ • Created Event │    │ • Active Cache  │    │ • JSON File     │    │ • Task→CP Map   │                       │
│  │ • Notification  │    │ • LRU Policy    │    │ • Directory     │    │ • Worker→CP Map │                       │
│  │ • Integration   │    │ • Fast Access   │    │ • Backup Copy   │    │ • State→CP Map  │                       │
│  │ • Monitoring    │    │ • Sync Policy   │    │ • Atomic Write  │    │ • Time→CP Map   │                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│                                                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                      Task Execution Flow                                                      │  │
│  │                                                                                                               │  │
│  │  Step 1: Initialize                                                                                           │  │
│  │      │                                                                                                        │  │
│  │      ▼                                                                                                        │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Worker        │───▶│   Checkpoint    │───▶│   Execute       │───▶│   Update        │                   │  │
│  │  │   Assignment    │    │   Step 1        │    │   Work          │    │   Progress      │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Allocate      │    │ • Create CP     │    │ • Perform Task  │    │ • Update CP     │                   │  │
│  │  │ • Circuit Break │    │ • Set Active    │    │ • Generate Out  │    │ • Add Data      │                   │  │
│  │  │ • Trace Start   │    │ • Track Start   │    │ • Handle Errors │    │ • Update Meta   │                   │  │
│  │  │ • Checkpoint    │    │ • Store Context │    │ • Monitor       │    │ • Emit Events   │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │          │                       │                       │                       │                           │  │
│  │          │                       │                       │                       │                           │  │
│  │          ▼                       ▼                       ▼                       ▼                           │  │
│  │  Step 2: Process                                                                                              │  │
│  │          │                                                                                                    │  │
│  │          ▼                                                                                                    │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Continue      │───▶│   Checkpoint    │───▶│   Execute       │───▶│   Update        │                   │  │
│  │  │   Execution     │    │   Step 2        │    │   Next Step     │    │   Progress      │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Resume Work   │    │ • Complete CP 1 │    │ • Continue Task │    │ • Update CP 2   │                   │  │
│  │  │ • Check State   │    │ • Create CP 2   │    │ • Process Data  │    │ • Progress %    │                   │  │
│  │  │ • Validate      │    │ • Set Active    │    │ • Validate Out  │    │ • Timing Info   │                   │  │
│  │  │ • Monitor       │    │ • Store State   │    │ • Error Handle  │    │ • Emit Events   │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  │  Step N: Complete                                                                                             │  │
│  │          │                                                                                                    │  │
│  │          ▼                                                                                                    │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Finalize      │───▶│   Complete      │───▶│   Archive       │───▶│   Cleanup       │                   │  │
│  │  │   Task          │    │   Checkpoint    │    │   Results       │    │   Memory        │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Collect Results│    │ • Final CP     │    │ • Move to Done  │    │ • Clear Cache   │                   │  │
│  │  │ • Validate      │    │ • Set Complete  │    │ • Update Index  │    │ • Update Stats  │                   │  │
│  │  │ • Generate Report│    │ • Store Results │    │ • Backup        │    │ • Emit Complete │                   │  │
│  │  │ • Release Worker│    │ • Emit Event    │    │ • Compress      │    │ • Notify System │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Recovery Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      Recovery Flow Diagram                                                         │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                     │
│  Task Failure Detected                                                                                             │
│      │                                                                                                              │
│      ▼                                                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   Failure       │───▶│   Checkpoint    │───▶│   Analyze       │───▶│   Determine     │                       │
│  │   Detection     │    │   Failure       │    │   Failure       │    │   Recovery      │                       │
│  │                 │    │                 │    │                 │    │   Strategy      │                       │
│  │ • Error Caught  │    │ • Create Fail CP│    │ • Error Type    │    │ • Retry Logic   │                       │
│  │ • Context Saved │    │ • Store Error   │    │ • Context Info  │    │ • Worker Change │                       │
│  │ • State Captured│    │ • Emit Event    │    │ • History Check │    │ • Decomposition │                       │
│  │ • Worker Notify │    │ • Update Index  │    │ • Pattern Match │    │ • Manual Inter. │                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│                                                          │                       │                                │
│                                                          │                       │                                │
│                                                          ▼                       ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                      Recovery Strategies                                                      │  │
│  │                                                                                                               │  │
│  │  Strategy 1: Immediate Retry                                                                                  │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Restore       │───▶│   Resume        │───▶│   Execute       │───▶│   Monitor       │                   │  │
│  │  │   Checkpoint    │    │   Execution     │    │   From Point    │    │   Progress      │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Load Last CP  │    │ • Same Worker   │    │ • Continue Task │    │ • Watch Errors  │                   │  │
│  │  │ • Validate State│    │ • Same Context  │    │ • Apply Fixes   │    │ • Update CP     │                   │  │
│  │  │ • Set Restored  │    │ • Resume Logic  │    │ • Retry Counter │    │ • Success Check │                   │  │
│  │  │ • Emit Event    │    │ • Circuit Check │    │ • Timeout Watch │    │ • Failure Detect│                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  │  Strategy 2: Worker Reallocation                                                                              │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Release       │───▶│   Allocate      │───▶│   Transfer      │───▶│   Resume        │                   │  │
│  │  │   Failed Worker │    │   New Worker    │    │   Context       │    │   Execution     │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Mark Failed   │    │ • Find Available│    │ • Copy State    │    │ • New Worker    │                   │  │
│  │  │ • Circuit Break │    │ • Check Capacity│    │ • Transfer CP   │    │ • Same Task     │                   │  │
│  │  │ • Update Stats  │    │ • Assign Task   │    │ • Update Index  │    │ • Fresh Start   │                   │  │
│  │  │ • Emit Event    │    │ • Create CB     │    │ • Validate      │    │ • Monitor       │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  │  Strategy 3: Task Decomposition                                                                               │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Analyze       │───▶│   Decompose     │───▶│   Create        │───▶│   Execute       │                   │  │
│  │  │   Complexity    │    │   Task          │    │   Subtasks      │    │   Subtasks      │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Task Size     │    │ • Break Down    │    │ • Subtask CPs   │    │ • Parallel Exec │                   │  │
│  │  │ • Failure Point │    │ • Dependencies  │    │ • Hierarchy     │    │ • Progress Track│                   │  │
│  │  │ • History Check │    │ • Strategies    │    │ • Worker Assign │    │ • Merge Results │                   │  │
│  │  │ • Recommend     │    │ • Create Plan   │    │ • Index Update  │    │ • Validation    │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  │  Strategy 4: Manual Intervention                                                                              │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Generate      │───▶│   Notify        │───▶│   Wait for      │───▶│   Resume        │                   │  │
│  │  │   Report        │    │   Operators     │    │   Intervention  │    │   Execution     │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Error Details │    │ • Slack Alert   │    │ • Pause Task    │    │ • Apply Fix     │                   │  │
│  │  │ • Context Dump  │    │ • Email Report  │    │ • Preserve CP   │    │ • Validate      │                   │  │
│  │  │ • Suggested Fix │    │ • Dashboard     │    │ • Monitor Queue │    │ • Continue      │                   │  │
│  │  │ • Save State    │    │ • API Call      │    │ • Timeout Check │    │ • Report Back   │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                                     │
│  Recovery Success                                                                                                   │
│      │                                                                                                              │
│      ▼                                                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   Update        │───▶│   Complete      │───▶│   Analytics     │───▶│   Optimize      │                       │
│  │   Metrics       │    │   Task          │    │   Update        │    │   System        │                       │
│  │                 │    │                 │    │                 │    │                 │                       │
│  │ • Recovery Time │    │ • Final CP      │    │ • Recovery Stats│    │ • Learn Pattern │                       │
│  │ • Strategy Used │    │ • Success State │    │ • Failure Trends│    │ • Adjust Thresholds│                   │
│  │ • Cost Analysis │    │ • Clean State   │    │ • Worker Perf   │    │ • Improve Strategies│                   │
│  │ • Lessons       │    │ • Emit Events   │    │ • System Health │    │ • Update Policies│                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## State Transition Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Checkpoint State Transitions                                                    │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                     │
│                                  ┌─────────────────┐                                                              │
│                                  │     CREATED     │                                                              │
│                                  │                 │                                                              │
│                                  │ • Initial state │                                                              │
│                                  │ • Basic data    │                                                              │
│                                  │ • Metadata set  │                                                              │
│                                  │ • Worker assigned│                                                              │
│                                  └─────────────────┘                                                              │
│                                           │                                                                        │
│                                           │ start_execution()                                                      │
│                                           ▼                                                                        │
│                                  ┌─────────────────┐                                                              │
│                                  │     ACTIVE      │                                                              │
│                                  │                 │                                                              │
│                                  │ • Processing    │                                                              │
│                                  │ • Progress track│                                                              │
│                                  │ • Regular update│                                                              │
│                                  │ • Worker busy   │                                                              │
│                                  └─────────────────┘                                                              │
│                                      │         │                                                                  │
│                                      │         │                                                                  │
│                        success()     │         │     error()                                                     │
│                                      │         │                                                                  │
│                                      ▼         ▼                                                                  │
│                          ┌─────────────────┐ ┌─────────────────┐                                                │
│                          │   COMPLETED     │ │     FAILED      │                                                │
│                          │                 │ │                 │                                                │
│                          │ • Task done     │ │ • Error state   │                                                │
│                          │ • Results saved │ │ • Error info    │                                                │
│                          │ • Worker freed  │ │ • Context saved │                                                │
│                          │ • Archived      │ │ • Recovery data │                                                │
│                          └─────────────────┘ └─────────────────┘                                                │
│                                              │                                                                    │
│                                              │ restore()                                                          │
│                                              ▼                                                                    │
│                                    ┌─────────────────┐                                                            │
│                                    │    RESTORED     │                                                            │
│                                    │                 │                                                            │
│                                    │ • Loaded from   │                                                            │
│                                    │   storage       │                                                            │
│                                    │ • Ready for     │                                                            │
│                                    │   retry         │                                                            │
│                                    │ • Context       │                                                            │
│                                    │   rebuilt       │                                                            │
│                                    └─────────────────┘                                                            │
│                                              │                                                                    │
│                                              │ retry_execution()                                                  │
│                                              ▼                                                                    │
│                                    ┌─────────────────┐                                                            │
│                                    │     ACTIVE      │                                                            │
│                                    │   (retry)       │                                                            │
│                                    │                 │                                                            │
│                                    │ • Resumed       │                                                            │
│                                    │ • New attempt   │                                                            │
│                                    │ • Monitored     │                                                            │
│                                    │ • Tracked       │                                                            │
│                                    └─────────────────┘                                                            │
│                                                                                                                     │
│  Valid State Transitions:                                                                                          │
│  • CREATED → ACTIVE         (Normal execution start)                                                              │
│  • ACTIVE → COMPLETED       (Successful completion)                                                               │
│  • ACTIVE → FAILED          (Error during execution)                                                              │
│  • FAILED → RESTORED        (Recovery operation)                                                                  │
│  • RESTORED → ACTIVE        (Retry execution)                                                                     │
│  • CREATED → FAILED         (Immediate failure)                                                                   │
│                                                                                                                     │
│  Invalid State Transitions:                                                                                        │
│  • COMPLETED → ACTIVE       (Cannot restart completed task)                                                       │
│  • COMPLETED → FAILED       (Cannot fail completed task)                                                          │
│  • FAILED → COMPLETED       (Cannot complete failed task without retry)                                           │
│  • RESTORED → COMPLETED     (Must go through ACTIVE state)                                                        │
│  • RESTORED → FAILED        (Cannot fail restored task without retry)                                             │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Integration Architecture                                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              External Systems Integration                                                     │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │  │
│  │  │   Monitoring    │  │   Notifications │  │   Analytics     │  │   Backup        │  │   Compliance    │  │  │
│  │  │   Systems       │  │   Services      │  │   Platform      │  │   Services      │  │   Auditing      │  │  │
│  │  │                 │  │                 │  │                 │  │                 │  │                 │  │  │
│  │  │ • Prometheus    │  │ • Slack         │  │ • Grafana       │  │ • S3 Backup     │  │ • Audit Logs    │  │  │
│  │  │ • DataDog       │  │ • Email         │  │ • Kibana        │  │ • Version Ctrl  │  │ • Compliance    │  │  │
│  │  │ • New Relic     │  │ • PagerDuty     │  │ • Custom Dash   │  │ • Disaster Rec. │  │ • Security      │  │  │
│  │  │ • Custom        │  │ • Webhooks      │  │ • Reporting     │  │ • Archival      │  │ • Governance    │  │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  │  │
│  │           │                     │                     │                     │                     │          │  │
│  │           └─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┘          │  │
│  │                                 │                     │                     │                                │  │
│  └─────────────────────────────────┼─────────────────────┼─────────────────────┼────────────────────────────────┘  │
│                                    │                     │                     │                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                 API Integration Layer                                                        │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │  │
│  │  │   REST API      │  │   GraphQL API   │  │   WebSocket     │  │   Event Stream  │  │   Webhook       │  │  │
│  │  │   Endpoints     │  │   Interface     │  │   Real-time     │  │   Publisher     │  │   Handlers      │  │  │
│  │  │                 │  │                 │  │                 │  │                 │  │                 │  │  │
│  │  │ • CRUD Ops      │  │ • Query Builder │  │ • Live Updates  │  │ • Event Bus     │  │ • Callbacks     │  │  │
│  │  │ • Batch Ops     │  │ • Introspection │  │ • Notifications │  │ • Pub/Sub       │  │ • Integrations  │  │  │
│  │  │ • Authentication│  │ • Subscriptions │  │ • Bidirectional │  │ • Message Queue │  │ • Automation    │  │  │
│  │  │ • Authorization │  │ • Mutations     │  │ • Connection    │  │ • Event Routing │  │ • Triggers      │  │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  │  │
│  │           │                     │                     │                     │                     │          │  │
│  │           └─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┘          │  │
│  │                                 │                     │                     │                                │  │
│  └─────────────────────────────────┼─────────────────────┼─────────────────────┼────────────────────────────────┘  │
│                                    │                     │                     │                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                               Checkpoint Core Integration                                                    │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │  │
│  │  │   Enhanced      │  │   Task Master   │  │   Dynamic       │  │   Circuit       │  │   Execution     │  │  │
│  │  │   Orchestrator  │  │   Integration   │  │   Allocator     │  │   Breaker       │  │   Tracer        │  │  │
│  │  │                 │  │                 │  │                 │  │                 │  │                 │  │  │
│  │  │ • Task Context  │  │ • Task Sync     │  │ • Worker State  │  │ • Failure Track │  │ • Trace Events  │  │  │
│  │  │ • Workflow      │  │ • Status Update │  │ • Allocation CP │  │ • Recovery CP   │  │ • Checkpoint    │  │  │
│  │  │ • Checkpointing │  │ • Dependency    │  │ • Performance   │  │ • Health Check  │  │ • Correlation   │  │  │
│  │  │ • Recovery      │  │ • Progress Track│  │ • Optimization  │  │ • Circuit State │  │ • Analytics     │  │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘  │  │
│  │           │                     │                     │                     │                     │          │  │
│  │           └─────────────────────┼─────────────────────┼─────────────────────┼─────────────────────┘          │  │
│  │                                 │                     │                     │                                │  │
│  └─────────────────────────────────┼─────────────────────┼─────────────────────┼────────────────────────────────┘  │
│                                    │                     │                     │                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                               Message Flow Integration                                                       │  │
│  │                                                                                                               │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │  │
│  │  │   Input         │───▶│   Processing    │───▶│   Output        │───▶│   Notification  │                   │  │
│  │  │   Events        │    │   Pipeline      │    │   Events        │    │   Delivery      │                   │  │
│  │  │                 │    │                 │    │                 │    │                 │                   │  │
│  │  │ • Task Start    │    │ • Validation    │    │ • Progress      │    │ • Slack         │                   │  │
│  │  │ • Progress      │    │ • Filtering     │    │ • Completion    │    │ • Email         │                   │  │
│  │  │ • Completion    │    │ • Routing       │    │ • Failure       │    │ • Webhook       │                   │  │
│  │  │ • Failure       │    │ • Enrichment    │    │ • Recovery      │    │ • Dashboard     │                   │  │
│  │  │ • Recovery      │    │ • Aggregation   │    │ • Analytics     │    │ • Mobile        │                   │  │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                   │  │
│  │                                                                                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Component Interaction Flow                                                      │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                     │
│  User Request                                                                                                       │
│      │                                                                                                              │
│      ▼                                                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   CLI/API       │───▶│   Enhanced      │───▶│   Task Master   │───▶│   Task Queue    │                       │
│  │   Interface     │    │   Orchestrator  │    │   Integration   │    │   Management    │                       │
│  │                 │    │                 │    │                 │    │                 │                       │
│  │ • Parse Request │    │ • Plan Tasks    │    │ • Create Tasks  │    │ • Queue Tasks   │                       │
│  │ • Validate      │    │ • Analyze Deps  │    │ • Set Priorities│    │ • Dependencies  │                       │
│  │ • Route         │    │ • Allocate      │    │ • Update Status │    │ • Scheduling    │                       │
│  │ • Monitor       │    │ • Checkpoint    │    │ • Checkpoint    │    │ • Checkpoint    │                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│           │                       │                       │                       │                                │
│           │                       │                       │                       │                                │
│           ▼                       ▼                       ▼                       ▼                                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│  │   Progress      │    │   Checkpoint    │    │   Worker        │    │   Execution     │                       │
│  │   Monitoring    │    │   Manager       │    │   Pool          │    │   Engine        │                       │
│  │                 │    │                 │    │                 │    │                 │                       │
│  │ • Real-time     │    │ • Create CP     │    │ • Opus Manager  │    │ • Task Exec     │                       │
│  │ • Aggregation   │    │ • Update CP     │    │ • Sonnet Work.  │    │ • Error Handle  │                       │
│  │ • Visualization │    │ • Store CP      │    │ • Circuit Break │    │ • State Manage  │                       │
│  │ • Alerts        │    │ • Recover CP    │    │ • Health Check  │    │ • Checkpoint    │                       │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│                                   │                       │                       │                                │
│                                   │                       │                       │                                │
│                                   ▼                       ▼                       ▼                                │
│                          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                       │
│                          │   Storage       │    │   Event         │    │   Result        │                       │
│                          │   System        │    │   Broadcasting  │    │   Processing    │                       │
│                          │                 │    │                 │    │                 │                       │
│                          │ • File System   │    │ • State Changes │    │ • Validation    │                       │
│                          │ • Indexing      │    │ • Notifications │    │ • Aggregation   │                       │
│                          │ • Backup        │    │ • Integration   │    │ • Reporting     │                       │
│                          │ • Compression   │    │ • Monitoring    │    │ • Archival      │                       │
│                          └─────────────────┘    └─────────────────┘    └─────────────────┘                       │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

This comprehensive architecture diagram set provides a complete visual representation of the checkpoint system's design, including:

1. **System Overview**: Complete system architecture with all major components
2. **Data Flow**: How data moves through the system during normal operations
3. **Recovery Flow**: How the system handles failures and recovery scenarios
4. **State Transitions**: Valid state changes and business rules
5. **Integration Architecture**: How the system connects to external services and internal components
6. **Component Interaction**: How different system components interact and coordinate

The diagrams show the checkpoint system as a robust, well-integrated component that provides comprehensive state management, recovery capabilities, and monitoring features for the Claude Orchestrator system.