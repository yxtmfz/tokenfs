// Exercise the real metadata implementation, including access ordering within one second.
#define main tokenfs_daemon_entry_for_test
#include "../src/main.cpp"
#undef main
#include <cassert>
#include <atomic>
#include <future>
#include <map>

namespace {
struct TokenFSTestAccess {
  struct TelemetryProbe {
    sqlite3* db=nullptr;
    explicit TelemetryProbe(const fs::path& path) {
      assert(sqlite3_open(path.c_str(),&db)==SQLITE_OK);
      assert(sqlite3_busy_timeout(db,3000)==SQLITE_OK);
    }
    ~TelemetryProbe(){sqlite3_close(db);}
    void Exec(const char* sql){assert(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK);}
    uint64_t Metric(const char* name) {
      sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&st,nullptr)==SQLITE_OK);
      sqlite3_bind_text(st,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(st);
      assert(rc==SQLITE_ROW || rc==SQLITE_DONE);
      const uint64_t n=rc==SQLITE_ROW?sqlite3_column_int64(st,0):0;sqlite3_finalize(st);return n;
    }
    // Read both counters from one SQLite statement/snapshot, even while a
    // worker is committing. Two separate SELECTs can invent an ordering bug.
    std::pair<uint64_t,uint64_t> Counts() {
      sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT COALESCE((SELECT value FROM metrics WHERE name='background_submitted'),0),COALESCE((SELECT value FROM metrics WHERE name='background_completed'),0)",-1,&st,nullptr)==SQLITE_OK);
      assert(sqlite3_step(st)==SQLITE_ROW);
      const std::pair<uint64_t,uint64_t> n{sqlite3_column_int64(st,0),sqlite3_column_int64(st,1)};
      sqlite3_finalize(st);assert(n.second<=n.first);return n;
    }
    std::vector<std::string> Events() {
      std::vector<std::string> out;sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT action FROM policy_events ORDER BY seq",-1,&st,nullptr)==SQLITE_OK);
      int rc;while((rc=sqlite3_step(st))==SQLITE_ROW)out.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(st,0)));
      assert(rc==SQLITE_DONE);sqlite3_finalize(st);return out;
    }
  };
  template<class Predicate> static void Await(Predicate ready) {
    const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while(!ready()){assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();}
  }
  static Config DeferredConfig(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.batch_background_metrics=true;cfg.batch_policy_events=true;cfg.defer_background_submission_metrics=true;
    return cfg;
  }
  static void deferred_config_parse(const fs::path& root) {
    fs::create_directories(root);const auto path=root/"config.yaml";
    for(const char* value:{"false","true"}) {
      std::ofstream(path)<<"filesystem: {}\nbackends: []\ngpus: []\npolicy:\n  batch_background_metrics: true\n  defer_background_submission_metrics: "<<value<<"\n  precheck_shared_submission: "<<value<<"\n";
      const auto cfg=LoadConfig(path);
      assert(cfg.batch_background_metrics && cfg.defer_background_submission_metrics==(std::string(value)=="true"));
      assert(cfg.precheck_shared_submission==(std::string(value)=="true"));
    }
    std::ofstream(path)<<"filesystem: {}\nbackends: []\ngpus: []\n";
    assert(!LoadConfig(path).defer_background_submission_metrics);
    assert(!LoadConfig(path).precheck_shared_submission);
  }
  static void deferred_background_fence(const fs::path& root) {
    auto cfg=DeferredConfig(root);TokenFS filesystem(cfg);filesystem.Init();TelemetryProbe probe(cfg.metadata_db);
    std::unique_lock<std::mutex> fence(filesystem.flush_metrics_mu_);
    std::promise<void> started,proceed;auto started_f=started.get_future();auto proceed_f=proceed.get_future().share();
    auto submitted=std::async(std::launch::async,[&]{return filesystem.SubmitBackground([&]{
      started.set_value();proceed_f.wait();filesystem.AddBackgroundMetric("fence_value",7);
      filesystem.RecordPolicyEvent("fenced","/gpu0/k",0,4096,"test");
    });});
    // An accepted submission has no synchronous durable fence of its own.
    assert(submitted.wait_for(std::chrono::seconds(3))==std::future_status::ready && submitted.get());
    assert(started_f.wait_for(std::chrono::seconds(3))==std::future_status::ready);
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    proceed.set_value();
    Await([&]{std::lock_guard<std::mutex> lock(filesystem.buffered_metrics_mu_);return filesystem.buffered_metrics_["background_completed"]==1;});
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    assert(probe.Metric("fence_value")==0 && probe.Events().empty());
    fence.unlock();Await([&]{return probe.Counts().second==1;});
    assert(probe.Metric("fence_value")==7 && probe.Events()==std::vector<std::string>{"fenced"});
    // Both exception kinds are terminal task outcomes, each counted once.
    assert(filesystem.SubmitBackground([&]{filesystem.AddBackgroundMetric("fence_value",3);throw std::runtime_error("task injected");}));
    Await([&]{return probe.Counts().second==2;});
    assert(filesystem.SubmitBackground([&]{filesystem.AddBackgroundMetric("fence_value",5);throw 17;}));
    Await([&]{return probe.Counts().second==3;});
    filesystem.FlushBufferedMetrics();filesystem.FlushBufferedMetrics();
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{3,3}));
    assert(probe.Metric("fence_value")==15 && probe.Metric("background_error_count")==2);
  }
  static void deferred_background_failure_retry(const fs::path& root,int retry_mode) {
    auto cfg=DeferredConfig(root);auto filesystem=std::make_unique<TokenFS>(cfg);filesystem->Init();TelemetryProbe probe(cfg.metadata_db);
    const char* triggers[]={
      "CREATE TRIGGER reject_batch BEFORE INSERT ON metrics WHEN NEW.name='background_submitted' BEGIN SELECT RAISE(ABORT,'injected submitted'); END;",
      "CREATE TRIGGER reject_batch BEFORE INSERT ON policy_events WHEN NEW.action='reject' BEGIN SELECT RAISE(ABORT,'injected event'); END;",
      "CREATE TRIGGER reject_batch BEFORE INSERT ON metrics WHEN NEW.name='background_completed' BEGIN SELECT RAISE(ABORT,'injected completed'); END;"};
    probe.Exec(triggers[retry_mode]);
    assert(filesystem->SubmitBackground([&]{
      filesystem->AddBackgroundMetric("retry_value",7);
      filesystem->RecordPolicyEvent("reject","/gpu0/k",0,4096,"test");
      if(retry_mode==1)throw std::runtime_error("task and fence injected");
      if(retry_mode==2)throw 23;
    }));
    const uint64_t expected_errors=retry_mode?2:1;
    Await([&]{std::lock_guard<std::mutex> lock(filesystem->buffered_metrics_mu_);return filesystem->buffered_metrics_["background_error_count"]==expected_errors;});
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    assert(probe.Metric("retry_value")==0 && probe.Events().empty());
    {std::lock_guard<std::mutex> lock(filesystem->buffered_metrics_mu_);
      assert(filesystem->buffered_metrics_.at("background_submitted")==1);
      assert(filesystem->buffered_metrics_.at("background_completed")==1);}
    bool failed=false;try{filesystem->FlushBufferedMetrics();}catch(const std::runtime_error&){failed=true;}
    assert(failed && probe.Events().empty());
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    probe.Exec("DROP TRIGGER reject_batch;");
    if(retry_mode==0) {filesystem->FlushBufferedMetrics();filesystem->FlushBufferedMetrics();}
    if(retry_mode==1) {
      assert(filesystem->SubmitBackground([&]{filesystem->AddBackgroundMetric("retry_value",5);filesystem->RecordPolicyEvent("newer","/gpu0/k",0,4096,"test");}));
      Await([&]{return probe.Counts().second==2;});filesystem->FlushBufferedMetrics();
    }
    if(retry_mode==2)filesystem.reset(); // join, then the destructor's existing fence retries.
    const uint64_t expected_tasks=retry_mode==1?2:1;
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{expected_tasks,expected_tasks}));
    assert(probe.Metric("retry_value")==uint64_t(retry_mode==1?12:7));
    assert(probe.Metric("background_error_count")==expected_errors);
    assert(probe.Events()==(retry_mode==1?std::vector<std::string>{"reject","newer"}:std::vector<std::string>{"reject"}));
  }
  static void deferred_background_queue_shutdown(const fs::path& root) {
    auto cfg=DeferredConfig(root);auto filesystem=std::make_unique<TokenFS>(cfg);filesystem->Init();TelemetryProbe probe(cfg.metadata_db);
    std::atomic<unsigned> ran{0};std::promise<void> started,proceed;auto started_f=started.get_future();auto proceed_f=proceed.get_future().share();
    assert(filesystem->SubmitBackground([&]{started.set_value();proceed_f.wait();++ran;}));
    assert(started_f.wait_for(std::chrono::seconds(3))==std::future_status::ready);
    for(int i=0;i<64;++i)assert(filesystem->SubmitBackground([&]{++ran;}));
    assert(!filesystem->SubmitBackground([&]{assert(false);}));
    {std::lock_guard<std::mutex> lock(filesystem->background_mu_);filesystem->background_stopping_=true;}
    filesystem->background_cv_.notify_all();
    assert(!filesystem->SubmitBackground([&]{assert(false);}));
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    proceed.set_value();filesystem.reset(); // A real join, not submitted==completed polling.
    assert(ran==65 && (probe.Counts()==std::pair<uint64_t,uint64_t>{65,65}));
    assert(probe.Metric("background_queue_rejected")==2 && probe.Metric("background_error_count")==0);
  }
  static void deferred_failed_fence_handoff(const fs::path& root) {
    auto cfg=DeferredConfig(root);TokenFS filesystem(cfg);filesystem.Init();TelemetryProbe probe(cfg.metadata_db);
    // Model an ended task whose worker is descheduled in its outer catch.
    // A foreground retry must already have the failure signal in its batch.
    filesystem.AddBufferedMetric("background_submitted",1);filesystem.AddBufferedMetric("background_completed",1);
    probe.Exec("CREATE TRIGGER reject_handoff BEFORE INSERT ON metrics WHEN NEW.name='background_completed' BEGIN SELECT RAISE(ABORT,'injected handoff'); END;");
    std::promise<void> caught,finish;auto caught_f=caught.get_future();auto finish_f=finish.get_future().share();
    auto failed_fence=std::async(std::launch::async,[&]{
      try{filesystem.FlushBufferedMetrics(0,true);assert(false);}
      catch(const std::runtime_error&){caught.set_value();finish_f.wait();}
    });
    assert(caught_f.wait_for(std::chrono::seconds(3))==std::future_status::ready);
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    probe.Exec("DROP TRIGGER reject_handoff;");filesystem.FlushBufferedMetrics();
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{1,1}));
    assert(probe.Metric("background_error_count")==1);
    finish.set_value();failed_fence.get();filesystem.FlushBufferedMetrics();
    assert(probe.Metric("background_error_count")==1);
  }
  static void readonly_release_fence(const fs::path& root) {
    assert(!Config{}.defer_background_submission_metrics);
    auto invalid=DeferredConfig(root/"invalid");invalid.batch_background_metrics=false;bool rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    auto cfg=DeferredConfig(root);cfg.request_read_costs=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();TelemetryProbe probe(cfg.metadata_db);
    std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'x');
    fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[2048];
    assert(filesystem.Open("/gpu0/k",&fi)==0);
    assert(filesystem.Read("/gpu0/k",bytes,sizeof(bytes),0,&fi)==2048);
    probe.Exec("CREATE TRIGGER reject_release BEFORE INSERT ON metrics WHEN NEW.name='read_release_count' BEGIN SELECT RAISE(ABORT,'injected release'); END;");
    bool failed=false;try{filesystem.Release("/gpu0/k",&fi);}catch(const std::runtime_error&){failed=true;}
    assert(failed && filesystem.FindHandle(&fi)==nullptr);
    assert(probe.Metric("read_release_count")==0 && probe.Metric("read_bytes")==0);
    assert(filesystem.buffered_metrics_.at("read_release_count")==1);
    probe.Exec("DROP TRIGGER reject_release;");
    assert(filesystem.Release("/gpu0/k",&fi)==0); // unknown handle retries only the failed fence.
    assert(probe.Metric("read_release_count")==1 && probe.Metric("read_bytes")==2048);
    assert(filesystem.Release("/gpu0/k",&fi)==0 && probe.Metric("read_release_count")==1);
    fuse_file_info writable{};writable.flags=O_RDWR;
    assert(filesystem.Open("/gpu0/k",&writable)==0);
    assert(filesystem.Release("/gpu0/k",&writable)==0 && probe.Metric("read_release_count")==1);
  }
  static Config PrecheckConfig(const fs::path& root,int domains=3) {
    auto cfg=DeferredConfig(root);cfg.precheck_shared_submission=true;
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.measured_burst_reuse=true;
    cfg.adaptive_reuse_control=true;cfg.compact_measured_planning=true;cfg.bounded_cost_warmup=true;
    for(int gpu=0;gpu<domains;++gpu)
      cfg.gpus.push_back({gpu,"/gpu"+std::to_string(gpu),root/("local"+std::to_string(gpu)),8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});return cfg;
  }
  struct PrecheckFixture {
    Config cfg;TokenFS filesystem;FileMeta incoming;std::shared_ptr<ReadFillPool::Buffer> fill;
    explicit PrecheckFixture(const fs::path& root,int domains=3):cfg(PrecheckConfig(root,domains)),filesystem(cfg) {
      filesystem.Init();assert(filesystem.submission_precheck_ready_);
      incoming.logical_path="/gpu0/incoming";incoming.gpu_id=0;incoming.tier="remote";
      incoming.backend_id="remote";incoming.physical_path=root/"remote/gpu0/incoming";
      incoming.has_remote_copy=true;incoming.size_bytes=4096;incoming.state="COMMITTED";
      const std::string bytes(4096,'x');std::ofstream(incoming.physical_path)<<bytes;
      filesystem.metadata_.Upsert(incoming);int fd=open(incoming.physical_path.c_str(),O_RDONLY);assert(fd>=0);
      fill=filesystem.fills_.Acquire(incoming.logical_path,fd,4096);
      assert(fill && fill->Append(0,bytes.data(),bytes.size(),fd));close(fd);
      filesystem.measured_.ReadSample(false,4096,21000);
      filesystem.measured_.ReadSample(true,4096,10500);filesystem.measured_.CopySample(4096,8000);
    }
    void Resident(int domain,const std::string& key,const fs::path& alias={},uint64_t bytes=4096) {
      FileMeta meta=incoming;meta.logical_path="/gpu0/"+key;meta.physical_path=cfg.backends.at("remote").root/"gpu0"/key;
      meta.size_bytes=bytes;std::ofstream(meta.physical_path)<<std::string(bytes,'r');filesystem.metadata_.Upsert(meta);
      LocalReplica replica;replica.logical_path=meta.logical_path;replica.gpu_id=domain;replica.size_bytes=bytes;replica.state="READY";
      replica.physical_path=alias.empty()?cfg.gpus.at(domain).local_root/key:alias;
      std::ofstream(replica.physical_path)<<std::string(bytes,'r');filesystem.metadata_.UpsertLocalReplica(replica);
    }
    void FullDomain(int domain) {Resident(domain,"resident"+std::to_string(domain)+"a");Resident(domain,"resident"+std::to_string(domain)+"b");}
    void Full() {for(size_t gpu=0;gpu<cfg.gpus.size();++gpu)FullDomain(gpu);}
    void Observe(unsigned n) {while(n--)filesystem.measured_.Observe(0,incoming.logical_path,filesystem.MeasuredOptions());}
    bool Reject(int caller=0){return filesystem.PrecheckSharedSubmission(incoming,caller,fill);}
  };
  static void submission_precheck_decisions(const fs::path& root) {
    assert(!Config{}.precheck_shared_submission);
    PrecheckFixture f(root);f.Observe(1);
    assert(!f.Reject()); // Free capacity exploration is preserved.
    f.Full();assert(f.Reject());
    assert(!f.filesystem.PrecheckSharedSubmission(f.incoming,0,{})); // Partial/no capture remains original path.
    auto wrong=f.incoming;wrong.size_bytes=2048;
    assert(!f.filesystem.PrecheckSharedSubmission(wrong,0,f.fill));
    auto partial=f.incoming;partial.logical_path="/gpu0/partial";partial.physical_path=f.cfg.backends.at("remote").root/"gpu0/partial";
    const std::string bytes(4096,'p');std::ofstream(partial.physical_path)<<bytes;
    int fd=open(partial.physical_path.c_str(),O_RDONLY);assert(fd>=0);
    auto unfinished=f.filesystem.fills_.Acquire(partial.logical_path,fd,4096);
    assert(unfinished && !unfinished->Append(0,bytes.data(),2048,fd));
    assert(!f.filesystem.PrecheckSharedSubmission(partial,0,unfinished));
    std::ofstream(partial.physical_path,std::ios::trunc)<<std::string(2048,'z');
    assert(!unfinished->Append(2048,bytes.data()+2048,2048,fd));close(fd);
    assert(!f.filesystem.PrecheckSharedSubmission(partial,0,unfinished)); // Changed source failed capture validation.
    f.filesystem.ScheduleSharedPlacement(f.incoming,0,f.fill);
    {std::lock_guard<std::mutex> lock(f.filesystem.background_mu_);assert(f.filesystem.background_tasks_.empty());}
    assert(f.filesystem.buffered_metrics_["background_submitted"]==0);
    assert(f.filesystem.shared_placement_inflight_.empty());
    // No negative-key cache: the same object can become profitable later.
    f.Observe(7);assert(!f.Reject());
    f.filesystem.config_.precheck_shared_submission=false;assert(!f.Reject());
    f.filesystem.config_.precheck_shared_submission=true;f.filesystem.config_.measured_affinity_gate=true;
    assert(!f.Reject()); // Unsupported location-dependent estimates never use the common bound.
    assert(f.filesystem.buffered_metrics_.count("submission_precheck_us") && f.filesystem.buffered_metric_max_.count("submission_precheck_us_max"));
    auto sieve=PrecheckConfig(root/"sieve");sieve.measured_policy=false;sieve.shared_value_placement=false;sieve.shared_pool_cache=true;
    TokenFS pool(sieve);assert(!pool.SubmissionPrecheckSupported());
  }
  static void submission_precheck_ablations(const fs::path& root) {
    for(bool static_value:{false,true}) {
      PrecheckFixture f(root/(static_value?"static":"hotspot"));f.Full();f.Observe(2);
      f.filesystem.config_.measured_static_reuse_value=static_value;
      // Two sparse observations cover copying, but not Full's incoming noise.
      assert(f.Reject());f.filesystem.config_.measured_joint_admission=false;assert(!f.Reject());
    }
    PrecheckFixture f(root/"caller");f.FullDomain(0);f.Observe(1);
    assert(!f.Reject()); // A permitted noncaller still has headroom.
    f.filesystem.config_.shared_caller_only=true;
    assert(f.Reject(0) && !f.Reject(1) && !f.Reject(99));
  }
  static void submission_precheck_busy(const fs::path& root) {
    PrecheckFixture f(root);f.Full();f.Observe(1);
    auto returns_without_waiting=[&](std::mutex& mutex) {
      std::unique_lock<std::mutex> held(mutex);
      auto result=std::async(std::launch::async,[&]{return f.Reject();});
      assert(result.wait_for(std::chrono::seconds(3))==std::future_status::ready);
      assert(!result.get());
    };
    returns_without_waiting(f.filesystem.layout_mu_);
    returns_without_waiting(f.filesystem.metadata_.mu_);
    assert(f.Reject());
    assert(f.filesystem.buffered_metrics_["submission_precheck_layout_busy"]==1);
    assert(f.filesystem.buffered_metrics_["submission_precheck_metadata_fallback"]==1);
  }
  static void submission_precheck_metadata(const fs::path& root) {
    PrecheckFixture f(root/"malformed",1);f.Full();f.Observe(1);TelemetryProbe probe(f.cfg.metadata_db);
    assert(f.Reject());
    probe.Exec("UPDATE local_replicas SET size_bytes=-1 WHERE logical_path='/gpu0/resident0a';");assert(!f.Reject());
    probe.Exec("UPDATE local_replicas SET size_bytes=4096,gpu_id=99 WHERE logical_path='/gpu0/resident0a';");assert(!f.Reject());
    probe.Exec("UPDATE local_replicas SET gpu_id=0,physical_path='/outside/cache' WHERE logical_path='/gpu0/resident0a';");assert(!f.Reject());
    // A prefix string is not component containment (local0-else is outside).
    auto outside=f.cfg.gpus[0].local_root.string()+"-else/file";
    sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(probe.db,"UPDATE local_replicas SET physical_path=? WHERE logical_path='/gpu0/resident0a'",-1,&stmt,nullptr)==SQLITE_OK);
    sqlite3_bind_text(stmt,1,outside.c_str(),-1,SQLITE_TRANSIENT);assert(sqlite3_step(stmt)==SQLITE_DONE);sqlite3_finalize(stmt);assert(!f.Reject());
    PrecheckFixture duplicate(root/"duplicate",1);const auto physical=duplicate.cfg.gpus[0].local_root/"same";
    duplicate.Resident(0,"a",physical);duplicate.Resident(0,"b",physical);duplicate.Observe(1);
    assert(!duplicate.Reject()); // One 4 KiB path leaves 4 KiB headroom, not zero.
    TelemetryProbe dup_probe(duplicate.cfg.metadata_db);
    dup_probe.Exec("UPDATE local_replicas SET size_bytes=8192 WHERE logical_path='/gpu0/b';");
    assert(!duplicate.Reject()); // Conflicting duplicate metadata is unknown.
  }
  static void submission_precheck_startup(const fs::path& root) {
    auto disabled=[&](Config cfg){TokenFS filesystem(cfg);filesystem.Init();assert(!filesystem.submission_precheck_ready_);};
    auto cfg=PrecheckConfig(root/"same-root");cfg.gpus[1].local_root=cfg.gpus[0].local_root;disabled(cfg);
    cfg=PrecheckConfig(root/"nested");cfg.gpus[1].local_root=cfg.gpus[0].local_root/"nested";disabled(cfg);
    cfg=PrecheckConfig(root/"nonempty");fs::create_directories(cfg.gpus[0].local_root);std::ofstream(cfg.gpus[0].local_root/"old")<<'x';disabled(cfg);
    cfg=PrecheckConfig(root/"duplicate-domain");cfg.gpus[1].gpu_id=0;disabled(cfg);
    cfg=PrecheckConfig(root/"orphan-ready");
    {MetadataStore store(cfg.metadata_db);store.Open();LocalReplica orphan;
      orphan.logical_path="/gpu0/later";orphan.gpu_id=0;orphan.physical_path=cfg.gpus[0].local_root/"absent";
      orphan.size_bytes=8192;orphan.state="READY";store.UpsertLocalReplica(orphan);}
    TokenFS filesystem(cfg);filesystem.Init();assert(!filesystem.submission_precheck_ready_);
    FileMeta later;later.logical_path="/gpu0/later";later.gpu_id=0;later.tier="remote";later.state="COMMITTED";
    filesystem.metadata_.Upsert(later);assert(!filesystem.submission_precheck_ready_);
  }
  static void ram_first_routing(const fs::path& root,bool enabled,bool lean) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=true;
    cfg.retain_read_fill=true;cfg.capture_local_reads=true;cfg.ram_first_routing=enabled;
    cfg.read_fill_buffer_bytes=4096;cfg.readonly_canonical=true;cfg.peer_cache_reads=true;
    cfg.shared_pool_cache=true;cfg.checksum="fnv1a64";cfg.affinity_placement=false;
    cfg.lean_read_accounting=lean;cfg.measured_track_affinity=true;
    cfg.read_through_cache=true;cfg.read_through_min_reads=1000;cfg.local_eviction_policy="sieve";
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"peer",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    const auto source=root/"remote/gpu0/k",peer=root/"peer/k";
    const std::string payload(4096,'r');std::ofstream(source)<<payload;std::ofstream(peer)<<payload;
    FileMeta meta;meta.logical_path="/gpu0/k";meta.gpu_id=0;meta.tier="remote";meta.backend_id="remote";
    meta.physical_path=source;meta.has_remote_copy=true;meta.size_bytes=payload.size();meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    LocalReplica replica;replica.logical_path=meta.logical_path;replica.gpu_id=1;
    replica.physical_path=peer;replica.size_bytes=payload.size();replica.state="READY";
    replica.last_access_at=7;replica.created_at=7;filesystem.metadata_.UpsertLocalReplica(replica);
    filesystem.sieve_.Ready(1,meta.logical_path);
    filesystem.sieve_.Ready(1,"/gpu0/cold-peer");
    int source_fd=open(source.c_str(),O_RDONLY);assert(source_fd>=0);
    auto fill=filesystem.fills_.Acquire(meta.logical_path,source_fd,payload.size());
    assert(fill && fill->Append(0,payload.data(),payload.size(),source_fd));close(source_fd);
    filesystem.fills_.Retain(fill);fill.reset();
    auto read=[&](const char* expected_tier,char expected) {
      fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[4096];
      assert(filesystem.Open(meta.logical_path.c_str(),&fi)==0);
      assert(filesystem.FindHandle(&fi)->tier==expected_tier);
      assert(filesystem.Read(meta.logical_path.c_str(),bytes,sizeof(bytes),0,&fi)==4096);
      assert(std::string(bytes,sizeof(bytes))==std::string(4096,expected));
      assert(filesystem.Release(meta.logical_path.c_str(),&fi)==0);
    };
    read("inflight",'r');read("inflight",'r');
    // Upper-tier service must preserve the same SIEVE visited bit as the
    // legacy route, without fabricating a peer data read or disk timestamp.
    assert(filesystem.sieve_.Victim(1,{meta.logical_path,"/gpu0/cold-peer"})=="/gpu0/cold-peer");
    assert(filesystem.metadata_.Get(meta.logical_path)->read_count==2);
    assert(filesystem.measured_.Frequency(0,meta.logical_path)==2);
    const auto touched=filesystem.metadata_.GetLocalReplica(meta.logical_path,1)->last_access_at;
    assert(enabled?touched==7:touched!=7);
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto metric=[&](const char* name){sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&st,nullptr)==SQLITE_OK);
      sqlite3_bind_text(st,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(st);
      const uint64_t n=rc==SQLITE_ROW?sqlite3_column_int64(st,0):0;sqlite3_finalize(st);return n;};
    assert(metric("read_open_count")==2 && metric("inflight_read_open_count")==2);
    assert(metric("peer_cache_hit")==uint64_t(enabled?0:2));
    assert(metric("cross_gpu_local_replica_hit")==0);
    assert(metric("replica_touch_batched")==uint64_t(!enabled && lean?2:0));
    assert(metric("ram_first_routing_hit")==uint64_t(enabled?2:0));
    assert(metric("sieve_ram_logical_hit")==uint64_t(enabled?2:0));
    // A changed canonical identity must invalidate the old RAM capture, then
    // use the ordinary validated disk path. The peer is updated by the fixture.
    std::ofstream(root/"replacement")<<std::string(4096,'s');fs::rename(root/"replacement",source);
    std::ofstream(peer,std::ios::trunc)<<std::string(4096,'s');read("local",'s');
    assert(filesystem.metadata_.Get(meta.logical_path)->read_count==3);
    assert(filesystem.measured_.Frequency(0,meta.logical_path)==3);
    assert(metric("peer_cache_hit")==uint64_t(enabled?1:3));
    assert(metric("retained_capture_hit")==2 && metric("local_read_open_count")==1);
    assert(filesystem.fills_.PeakBytes()<=4096);
    fuse_file_info writable{};writable.flags=O_RDWR;
    assert(filesystem.Open(meta.logical_path.c_str(),&writable)==-EROFS);
    assert(filesystem.metadata_.Get(meta.logical_path)->read_count==3);
    sqlite3_close(db);
    auto invalid=cfg;invalid.ram_first_routing=true;invalid.retain_read_fill=false;bool rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    invalid=cfg;invalid.private_cache_domains=true;rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
  }
  static void sieve_ram_permissions(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.local_eviction_policy="sieve";
    for(int gpu=0;gpu<3;++gpu)cfg.gpus.push_back({gpu,"/gpu"+std::to_string(gpu),root/("local"+std::to_string(gpu)),8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    auto resident=[&](int domain,const std::string& key,const std::string& state="READY",bool indexed=true) {
      LocalReplica replica;replica.logical_path=key;replica.gpu_id=domain;replica.state=state;
      replica.physical_path=root/("local"+std::to_string(domain))/fs::path(key).filename();
      replica.size_bytes=1;replica.created_at=7;replica.last_access_at=7;
      fs::create_directories(replica.physical_path.parent_path());std::ofstream(replica.physical_path)<<'x';
      filesystem.metadata_.UpsertLocalReplica(replica);
      if(indexed)filesystem.sieve_.Ready(domain,key);
      filesystem.sieve_.Ready(domain,key+"-cold");
    };
    auto victim=[&](int domain,const std::string& key){return filesystem.sieve_.Victim(domain,{key,key+"-cold"});};
    resident(1,"/gpu0/peer");
    assert(filesystem.HitSieveLogicalResident("/gpu0/peer",0,0,false));
    assert(victim(1,"/gpu0/peer")=="/gpu0/peer-cold");
    resident(1,"/gpu0/no-peer");filesystem.config_.peer_cache_reads=false;
    assert(!filesystem.HitSieveLogicalResident("/gpu0/no-peer",0,0,false));
    assert(victim(1,"/gpu0/no-peer")=="/gpu0/no-peer");filesystem.config_.peer_cache_reads=true;
    resident(1,"/gpu0/private");filesystem.config_.private_cache_domains=true;
    assert(!filesystem.HitSieveLogicalResident("/gpu0/private",0,0,false));
    assert(victim(1,"/gpu0/private")=="/gpu0/private");
    filesystem.sieve_.Ready(0,"/gpu0/owner-private");filesystem.sieve_.Ready(0,"/gpu0/owner-private-cold");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/owner-private",0,2,true));
    assert(victim(0,"/gpu0/owner-private")=="/gpu0/owner-private");
    resident(2,"/gpu0/caller-private");
    assert(filesystem.HitSieveLogicalResident("/gpu0/caller-private",0,2,false));
    assert(victim(2,"/gpu0/caller-private")=="/gpu0/caller-private-cold");
    filesystem.config_.private_cache_domains=false;
    resident(2,"/gpu0/priority");filesystem.sieve_.Ready(0,"/gpu0/priority");filesystem.sieve_.Ready(0,"/gpu0/priority-cold");
    assert(filesystem.HitSieveLogicalResident("/gpu0/priority",0,2,true));
    assert(victim(2,"/gpu0/priority")=="/gpu0/priority-cold");
    assert(victim(0,"/gpu0/priority")=="/gpu0/priority");
    resident(1,"/gpu0/not-ready","CREATING");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/not-ready",0,0,false));
    assert(victim(1,"/gpu0/not-ready")=="/gpu0/not-ready");
    resident(1,"/gpu0/not-published","READY",false);
    assert(!filesystem.HitSieveLogicalResident("/gpu0/not-published",0,0,false));
    resident(9,"/gpu0/unknown");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/unknown",0,0,false));
    assert(victim(9,"/gpu0/unknown")=="/gpu0/unknown");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/peer",0,9,false));
  }
  static void aligned_tail_reads(const fs::path& root,bool enabled) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.backend_direct_io=true;cfg.reuse_direct_read_tail=enabled;
    cfg.request_read_costs=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    std::string payload(8192,'\0');for(size_t i=0;i<payload.size();++i)payload[i]=char(i%251);
    std::ofstream(root/"remote/gpu0/k",std::ios::binary).write(payload.data(),payload.size());
    fuse_file_info fi{};fi.flags=O_RDONLY;assert(filesystem.Open("/gpu0/k",&fi)==0);
    char bytes[4096];size_t offset=0;
    for(size_t amount:{4048u,48u,4048u,48u,4096u}) {
      const int n=filesystem.Read("/gpu0/k",bytes,amount,offset,&fi);
      assert(n>=0 && size_t(n)==std::min(amount,payload.size()-offset));
      assert(std::string(bytes,size_t(n))==payload.substr(offset,size_t(n)));offset+=size_t(n);
    }
    assert(filesystem.Release("/gpu0/k",&fi)==0 && filesystem.direct_read_tail_handles_==0);
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto metric=[&](const char* name){sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&st,nullptr)==SQLITE_OK);
      sqlite3_bind_text(st,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(st);
      const uint64_t n=rc==SQLITE_ROW?sqlite3_column_int64(st,0):0;sqlite3_finalize(st);return n;};
    assert(metric("read_bytes")==8192 && metric("read_ops")==5);
    assert(metric("request_cost_remote_samples")==1 && metric("request_cost_remote_bytes")==8192);
    assert(metric("direct_backend_pread_ops")==uint64_t(enabled?3:5));
    assert(metric("direct_backend_pread_bytes")==uint64_t(enabled?8192:16384));
    assert(metric("direct_read_tail_hits")==uint64_t(enabled?2:0));
    assert(metric("direct_read_tail_bytes")==uint64_t(enabled?96:0));
    assert(metric("direct_read_tail_buffer_bytes_peak")==uint64_t(enabled?4096:0));
    assert(metric("read_release_count")==1);
    assert(filesystem.Release("/gpu0/k",&fi)==0 && metric("read_release_count")==1);
    sqlite3_close(db);
  }
  static void background_metric_fence(const fs::path& root,bool batched) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.batch_background_metrics=batched;
    TokenFS filesystem(cfg);filesystem.Init();
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto metric=[&](const char* name){
      sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&stmt,nullptr)==SQLITE_OK);
      sqlite3_bind_text(stmt,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(stmt);
      uint64_t value=rc==SQLITE_ROW?sqlite3_column_int64(stmt,0):0;sqlite3_finalize(stmt);return value;
    };
    for(int pass=1;pass<=3;++pass) {
      assert(filesystem.SubmitBackground([&]{filesystem.AddBackgroundMetric("fence_value",7);}));
      const auto limit=std::chrono::steady_clock::now()+std::chrono::seconds(3);
      while(metric("background_completed")<uint64_t(pass)) {
        assert(std::chrono::steady_clock::now()<limit);std::this_thread::yield();
      }
      // A durable completion must never get ahead of its batched counters.
      assert(metric("fence_value")==uint64_t(pass*7));
    }
    assert(metric("background_error_count")==0);sqlite3_close(db);
  }
  static void telemetry_retry_and_release_lock(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.batch_background_metrics=true;cfg.batch_policy_events=true;
    cfg.request_read_costs=true;cfg.readonly_canonical=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto exec=[&](const char* sql){assert(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK);};
    auto events=[&]{std::vector<std::string> out;sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT action FROM policy_events ORDER BY seq",-1,&st,nullptr)==SQLITE_OK);
      while(sqlite3_step(st)==SQLITE_ROW)out.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(st,0)));
      sqlite3_finalize(st);return out;};
    exec("CREATE TRIGGER reject_event BEFORE INSERT ON policy_events WHEN NEW.action='reject' BEGIN SELECT RAISE(ABORT,'injected'); END;");
    filesystem.AddBufferedMetric("retry_delta",7);filesystem.SetBufferedMetricMax("retry_peak",9);
    filesystem.RecordPolicyEvent("first","/gpu0/k",0,4096,"test",-3.5);
    filesystem.RecordPolicyEvent("reject","/gpu0/k",0,4096,"test");
    bool failed=false;try{filesystem.FlushBufferedMetrics(1);}catch(const std::runtime_error&){failed=true;}
    assert(failed && events().empty());
    assert(filesystem.buffered_metrics_.at("retry_delta")==7);
    assert(filesystem.buffered_metric_max_.at("retry_peak")==9);
    assert(filesystem.buffered_metrics_["background_completed"]==0);
    filesystem.RecordPolicyEvent("newer","/gpu0/k",0,4096,"test");
    exec("DROP TRIGGER reject_event;");filesystem.FlushBufferedMetrics();filesystem.FlushBufferedMetrics();
    assert((events()==std::vector<std::string>{"first","reject","newer"}));
    // Completion is durable only after the event batch, for the real worker.
    assert(filesystem.SubmitBackground([&]{filesystem.RecordPolicyEvent("background","/gpu0/k",0,0,"test");}));
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while(true) {
      sqlite3_stmt* st=nullptr;assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name='background_completed'",-1,&st,nullptr)==SQLITE_OK);
      const bool done=sqlite3_step(st)==SQLITE_ROW && sqlite3_column_int64(st,0)==1;sqlite3_finalize(st);
      if(done)break;assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();
    }
    assert(events().back()=="background");
    std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'x');
    fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[2048];
    assert(filesystem.Open("/gpu0/k",&fi)==0);
    assert(filesystem.Read("/gpu0/k",bytes,sizeof(bytes),0,&fi)==2048);
    // Hold the telemetry fence. A partial read accounts its sample in Release;
    // after that marker, the handle table must become available even though
    // Release is still waiting for this fence. The old implementation fails.
    std::unique_lock<std::mutex> fence(filesystem.flush_metrics_mu_);
    auto released=std::async(std::launch::async,[&]{return filesystem.Release("/gpu0/k",&fi);});
    const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    bool accounted=false;
    while(!accounted) {
      {std::lock_guard<std::mutex> lock(filesystem.buffered_metrics_mu_);accounted=filesystem.buffered_metrics_["request_cost_remote_samples"]==1;}
      assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();
    }
    while(!filesystem.handles_mu_.try_lock()) {assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();}
    assert(filesystem.handles_.empty());filesystem.handles_mu_.unlock();
    assert(released.wait_for(std::chrono::milliseconds(0))==std::future_status::timeout);
    fence.unlock();assert(released.get()==0);sqlite3_close(db);
  }
  static void inflight_reads(const fs::path& root,bool enabled,bool retained=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=enabled;cfg.retain_read_fill=retained;cfg.capture_local_reads=retained;cfg.read_fill_buffer_bytes=4096;cfg.batch_background_metrics=true;
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_pool_cache=true;cfg.checksum="fnv1a64";
    cfg.backend_direct_io=true;cfg.affinity_placement=false;cfg.lean_read_accounting=true;
    cfg.read_through_cache=true;cfg.read_through_min_reads=1;cfg.local_eviction_policy="sieve";
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'z');
    // Deterministically put placement behind a barrier, without sleeps or
    // changing the production state machine. The next open must stay correct
    // before READY, after READY, and while its own memory pin remains live.
    std::promise<void> started,proceed;auto started_f=started.get_future();
    auto proceed_f=proceed.get_future().share();
    assert(filesystem.SubmitBackground([&]{started.set_value();proceed_f.wait();}));started_f.wait();
    fuse_file_info a{},b{},c{};a.flags=b.flags=c.flags=O_RDONLY;char bytes[4096]{};
    assert(filesystem.Open("/gpu0/k",&a)==0);
    assert(filesystem.Read("/gpu0/k",bytes,4096,0,&a)==4096);
    assert(filesystem.Release("/gpu0/k",&a)==0);
    assert(filesystem.metadata_.Get("/gpu0/k")->tier=="remote");
    assert(filesystem.Open("/gpu0/k",&b)==0);
    assert(filesystem.FindHandle(&b)->tier==(enabled?"inflight":"remote"));
    assert(filesystem.Read("/gpu0/k",bytes,2048,0,&b)==2048);
    assert(filesystem.Read("/gpu0/k",bytes+2048,2048,2048,&b)==2048);
    assert(std::string(bytes,4096)==std::string(4096,'z'));
    assert(filesystem.Read("/gpu0/k",bytes,4096,4096,&b)==0);
    assert(filesystem.metadata_.Get("/gpu0/k")->tier=="remote");
    proceed.set_value();std::promise<void> drained;auto drained_f=drained.get_future();
    assert(filesystem.SubmitBackground([&]{drained.set_value();}));drained_f.wait();
    assert(filesystem.metadata_.Get("/gpu0/k")->tier=="local");
    assert(filesystem.Open("/gpu0/k",&c)==0 && filesystem.FindHandle(&c)->tier==(retained?"inflight":"local"));
    assert(filesystem.Read("/gpu0/k",bytes,4096,0,&c)==4096);
    assert(filesystem.Release("/gpu0/k",&c)==0);
    if(enabled)assert(filesystem.fills_.UsedBytes()==4096);
    assert(filesystem.Release("/gpu0/k",&b)==0 && filesystem.fills_.UsedBytes()==(retained?4096:0));
    sqlite3* conn=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&conn)==SQLITE_OK);
    sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(conn,"SELECT name,value FROM metrics",-1,&stmt,nullptr)==SQLITE_OK);
    std::map<std::string,uint64_t> m;
    while(sqlite3_step(stmt)==SQLITE_ROW)m[reinterpret_cast<const char*>(sqlite3_column_text(stmt,0))]=sqlite3_column_int64(stmt,1);
    sqlite3_finalize(stmt);sqlite3_close(conn);
    assert(m["read_bytes"]==12288 && m["read_local_bytes"]==(retained?0:4096));
    assert(m["read_remote_bytes"]==(enabled?4096:8192) && m["read_inflight_bytes"]==(enabled?(retained?8192:4096):0));
    assert(m["request_cost_inflight_samples"]==(enabled?(retained?2:1):0));
    if(retained) {
      std::ofstream(root/"remote/gpu0/pressure")<<std::string(4096,'p');
      int pressure=open((root/"remote/gpu0/pressure").c_str(),O_RDONLY);
      auto pin=filesystem.fills_.Acquire("pressure",pressure,4096);assert(pin);pin.reset();close(pressure);
      fuse_file_info local{},ram{};local.flags=ram.flags=O_RDONLY;
      assert(filesystem.Open("/gpu0/k",&local)==0 && filesystem.FindHandle(&local)->tier=="local");
      assert(filesystem.Read("/gpu0/k",bytes,4096,0,&local)==4096);
      assert(filesystem.Release("/gpu0/k",&local)==0);
      assert(filesystem.Open("/gpu0/k",&ram)==0 && filesystem.FindHandle(&ram)->tier=="inflight");
      assert(filesystem.Read("/gpu0/k",bytes,4096,0,&ram)==4096 && std::string(bytes,4096)==std::string(4096,'z'));
      assert(filesystem.Release("/gpu0/k",&ram)==0);
      assert(filesystem.shared_placement_inflight_.empty());
    }
    auto invalid=cfg;invalid.shared_caller_only=true;bool rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    invalid=cfg;invalid.foreground_read_fill=false;invalid.coalesce_pending_reads=true;rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
  }
  static void retained_rejected(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=true;cfg.retain_read_fill=true;
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_pool_cache=true;cfg.checksum="fnv1a64";
    cfg.backend_direct_io=true;cfg.affinity_placement=false;cfg.lean_read_accounting=true;
    cfg.read_through_cache=true;cfg.read_through_min_reads=1000;cfg.local_eviction_policy="sieve";
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'q');
    for(int i=0;i<3;++i) {
      fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[4096]{};
      assert(filesystem.Open("/gpu0/k",&fi)==0);
      assert(filesystem.FindHandle(&fi)->tier==(i?"inflight":"remote"));
      assert(filesystem.Read("/gpu0/k",bytes,4096,0,&fi)==4096 && std::string(bytes,4096)==std::string(4096,'q'));
      assert(filesystem.Release("/gpu0/k",&fi)==0);
      assert(filesystem.metadata_.Get("/gpu0/k")->tier=="remote");
      assert(filesystem.shared_placement_inflight_.empty());
    }
    assert(filesystem.fills_.UsedBytes()==4096);
  }
  static void foreground_fill(const fs::path& root,int threshold,bool adaptive=false,bool incremental=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.incremental_copy_cost=incremental;cfg.batch_background_metrics=true;
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.readonly_canonical=true;cfg.peer_cache_reads=true;
    cfg.shared_pool_cache=!adaptive;cfg.shared_value_placement=adaptive;cfg.checksum="fnv1a64";
    cfg.backend_direct_io=true;cfg.affinity_placement=false;cfg.lean_read_accounting=true;
    cfg.speculative_copy_may_evict=true;cfg.local_eviction_policy=adaptive?"value_aware":"sieve";
    cfg.read_through_cache=!adaptive;cfg.read_through_min_reads=threshold;
    cfg.measured_policy=adaptive;cfg.measured_causal_window=adaptive;cfg.compact_measured_planning=adaptive;
    cfg.measured_burst_reuse=adaptive;cfg.adaptive_reuse_control=adaptive;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"peer",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    if(adaptive){filesystem.measured_.ReadSample(false,4096,1000000);filesystem.measured_.ReadSample(true,4096,1);filesystem.measured_.CopySample(4096,10);}
    auto drain=[&]{std::promise<void> done;auto ready=done.get_future();assert(filesystem.SubmitBackground([&]{done.set_value();}));ready.wait();};
    for(const std::string key:{"full","partial","reordered","oversize"}) {
      const size_t size=key=="oversize"?12288:4096;
      std::ofstream(root/"remote/gpu0"/key)<<std::string(size,'k');
      for(int pass=0;pass<threshold;++pass) {
        const auto path="/gpu0/"+key;fuse_file_info fi{};fi.flags=O_RDONLY;
        assert(filesystem.Open(path.c_str(),&fi)==0);
        char bytes[12288];
        if(key=="partial")assert(filesystem.Read(path.c_str(),bytes,1024,0,&fi)==1024);
        else if(key=="reordered")assert(filesystem.Read(path.c_str(),bytes,2048,2048,&fi)==2048);
        else {
          assert(filesystem.Read(path.c_str(),bytes,size/2,0,&fi)==int(size/2));
          assert(filesystem.metadata_.Get(path)->tier=="remote"); // No partial READY.
          assert(filesystem.Read(path.c_str(),bytes,size/2,size/2,&fi)==int(size/2));
        }
        assert(filesystem.Release(path.c_str(),&fi)==0);drain();
        auto meta=*filesystem.metadata_.Get(path);
        auto peer=filesystem.ReadablePeer(path,-1);
        if(pass+1<threshold || key=="oversize")assert(meta.tier=="remote" && !peer);
        else {assert(meta.tier=="local" || peer);assert(filesystem.ChecksumFile(meta.tier=="local"?meta.physical_path:peer->physical_path)==filesystem.ChecksumFile(root/"remote/gpu0"/key));}
        assert(filesystem.fills_.UsedBytes()==0);
      }
    }
    // Both destination types use the same verified capture, including peer READY.
    auto source=root/"remote/gpu0/peerfill";std::ofstream(source)<<std::string(4096,'p');
    int fd=open(source.c_str(),O_RDONLY);auto fill=filesystem.fills_.Acquire("/gpu0/peerfill",fd,4096);
    assert(fill && fill->Append(0,std::string(4096,'p').data(),4096,fd));close(fd);
    FileMeta meta;meta.logical_path="/gpu0/peerfill";meta.gpu_id=0;meta.tier="remote";
    meta.physical_path=source;meta.has_remote_copy=true;meta.size_bytes=4096;meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    filesystem.CreateCrossGpuReplica(cfg.gpus[1],cfg.gpus[0],"peerfill",meta,fill);
    auto peer=filesystem.metadata_.GetLocalReplica(meta.logical_path,1);assert(peer && peer->state=="READY");
    assert(filesystem.ChecksumFile(peer->physical_path)==filesystem.ChecksumFile(source));
    auto tmp=root/"manual-copy";std::error_code ec;
    assert(filesystem.CopyOrFill(source,tmp,4096,fill,ec) && !ec);
    std::ofstream(tmp,std::ios::binary|std::ios::trunc)<<"corruption";
    assert(filesystem.ChecksumFile(tmp)!=std::optional<std::string>(fill->Checksum()));
    std::ofstream(root/"replacement")<<std::string(4096,'q');fs::rename(root/"replacement",source);
    ec.clear();assert(!filesystem.CopyOrFill(source,tmp,4096,fill,ec) && !ec);
    assert(filesystem.ChecksumFile(tmp)==filesystem.ChecksumFile(source));
    if(adaptive) {
      filesystem.FlushBufferedMetrics();
      sqlite3* conn=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&conn)==SQLITE_OK);
      sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(conn,"SELECT name,value FROM metrics WHERE name LIKE 'copy_cost_%'",-1,&stmt,nullptr)==SQLITE_OK);
      std::map<std::string,uint64_t> costs;
      while(sqlite3_step(stmt)==SQLITE_ROW)costs[reinterpret_cast<const char*>(sqlite3_column_text(stmt,0))]=sqlite3_column_int64(stmt,1);
      sqlite3_finalize(stmt);sqlite3_close(conn);
      assert(costs["copy_cost_samples"]>0 && costs["copy_cost_remaining_us"]>0);
      assert(costs["copy_cost_full_us"]==costs["copy_cost_remaining_us"]+costs["copy_cost_planning_us"]+costs["copy_cost_capture_us"]);
      assert(costs["copy_cost_charged_us"]==costs[incremental?"copy_cost_remaining_us":"copy_cost_full_us"]);
    }
    auto invalid=cfg;invalid.readonly_canonical=false;bool rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
  }
  static void request_trace_roundtrip(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.request_read_costs=true;
    cfg.request_trace_path=(root/"trace.json").string();cfg.checksum="fnv1a64";
    cfg.readonly_canonical=true;cfg.backend_direct_io=true;cfg.affinity_placement=false;
    cfg.read_through_cache=true;cfg.read_through_min_reads=100;cfg.lean_read_accounting=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",16384,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    {
      TokenFS filesystem(cfg);filesystem.Init();
      std::ofstream(root/"remote/gpu0/k")<<std::string(8192,'z');
      for(int pass=0;pass<2;++pass){
        fuse_file_info fi{};fi.flags=O_RDONLY;
        assert(filesystem.Open("/gpu0/k",&fi)==0);
        char buffer[8192];assert(filesystem.Read("/gpu0/k",buffer,8192,0,&fi)==8192);
        assert(std::string(buffer,8192)==std::string(8192,'z'));
        assert(filesystem.Read("/gpu0/k",buffer,8192,8192,&fi)==0);
        assert(filesystem.Release("/gpu0/k",&fi)==0);
        if(pass==0){auto meta=*filesystem.metadata_.Get("/gpu0/k");assert(filesystem.PromoteToLocal(cfg.gpus[0],"k",meta,"promote")==0);}
      }
      assert(!fs::exists(cfg.request_trace_path));
    }
    auto trace=YAML::LoadFile(cfg.request_trace_path);assert(trace["dropped"].as<int>()==0);
    std::map<uint64_t,uint64_t> bytes;int opens=0,releases=0,copies=0;
    for(auto e:trace["events"]){
      auto op=e["op"].as<std::string>();
      assert(e["end_ns"].as<uint64_t>()>=e["start_ns"].as<uint64_t>());
      if(op=="open")++opens;
      if(op=="release")++releases;
      if(op=="copy_pipeline")++copies;
      if(op=="read"){bytes[e["handle"].as<uint64_t>()]+=e["bytes"].as<uint64_t>();assert(e["pread_ns"].as<uint64_t>()>0);}
    }
    assert(opens==2 && releases==2 && copies==1 && bytes.size()==2);
    for(auto [handle,n]:bytes)assert(n==8192 && handle>0);
    sqlite3* db=nullptr;assert(sqlite3_open_v2(cfg.metadata_db.c_str(),&db,SQLITE_OPEN_READONLY,nullptr)==SQLITE_OK);
    sqlite3_stmt* stmt=nullptr;
    assert(sqlite3_prepare_v2(db,"SELECT name,value FROM metrics WHERE name LIKE 'request_cost_%';",-1,&stmt,nullptr)==SQLITE_OK);
    std::map<std::string,uint64_t> metrics;
    while(sqlite3_step(stmt)==SQLITE_ROW)metrics[reinterpret_cast<const char*>(sqlite3_column_text(stmt,0))]=sqlite3_column_int64(stmt,1);
    sqlite3_finalize(stmt);sqlite3_close(db);
    assert(metrics["request_cost_local_samples"]==1 && metrics["request_cost_remote_samples"]==1);
    assert(metrics["request_cost_local_bytes"]==8192 && metrics["request_cost_remote_bytes"]==8192);
  }
  static void shared_placement(const fs::path& root,bool compact=false,bool adaptive=false,bool caller_only=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=compact;cfg.measured_cost=false;cfg.checksum="fnv1a64";
    cfg.speculative_copy_may_evict=true;
    cfg.adaptive_reuse_control=adaptive;cfg.measured_burst_reuse=adaptive;cfg.measured_cost=adaptive;
    cfg.shared_caller_only=caller_only;
    for(int id=0;id<3;++id)cfg.gpus.push_back({id,"/gpu"+std::to_string(id),root/("local"+std::to_string(id)),1024,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    if(adaptive){filesystem.measured_.ReadSample(false,1024,1000000);filesystem.measured_.ReadSample(true,1024,1);filesystem.measured_.CopySample(1024,20);}
    for(const auto& key:{"hot","incoming"}) {
      auto remote=root/"remote/gpu0"/key;std::ofstream(remote)<<std::string(1024,key[0]);
      FileMeta meta;meta.logical_path=std::string("/gpu0/")+key;meta.gpu_id=0;
      meta.tier="remote";meta.physical_path=remote;meta.backend_id="remote";
      meta.size_bytes=1024;meta.has_remote_copy=true;meta.state="COMMITTED";filesystem.metadata_.Upsert(meta);
    }
    for(int i=0;i<16;++i)filesystem.measured_.Observe(0,"/gpu0/hot",filesystem.MeasuredOptions(),true);
    filesystem.PlaceShared("/gpu0/hot",0);
    assert(filesystem.metadata_.Get("/gpu0/hot")->tier=="local");
    for(int i=0;i<4;++i)filesystem.measured_.Observe(0,"/gpu0/incoming",filesystem.MeasuredOptions(),false);
    filesystem.PlaceShared("/gpu0/incoming",0); // Caller is full: use free peer capacity.
    auto replica=filesystem.metadata_.GetLocalReplica("/gpu0/incoming",1);
    if(caller_only) {
      assert(!replica && !filesystem.metadata_.GetLocalReplica("/gpu0/incoming",2));
      assert(filesystem.metadata_.Get("/gpu0/incoming")->tier=="remote");
      assert(filesystem.metadata_.Get("/gpu0/hot")->tier=="local");
      return;
    }
    assert(replica && replica->state=="READY");
    assert(filesystem.metadata_.Get("/gpu0/hot")->tier=="local");
    assert(filesystem.MarginalCoverage(*filesystem.metadata_.Get("/gpu0/incoming"),1)==1);
    auto copy=*replica;copy.gpu_id=2;copy.physical_path=root/"local2/incoming";
    fs::copy_file(replica->physical_path,copy.physical_path);filesystem.metadata_.UpsertLocalReplica(copy);
    assert(filesystem.MarginalCoverage(*filesystem.metadata_.Get("/gpu0/incoming"),1)==0);
    if(compact) {
      const auto snap=filesystem.SnapshotMeasuredResidents("");
      for(int location:{1,2}) {
        const auto& items=snap.at(location);
        auto item=std::find_if(items.begin(),items.end(),[](const auto& i){return i.key=="/gpu0/incoming";});
        assert(item!=items.end() && item->coverage==0);
      }
    }
    fs::remove(copy.physical_path);filesystem.metadata_.RemoveLocalReplica(copy.logical_path,2);
    filesystem.PlaceShared("/gpu0/incoming",2); // Execution-time coverage prevents duplication.
    assert(!filesystem.metadata_.GetLocalReplica("/gpu0/incoming",2));
    assert(filesystem.MarginalCoverage(*filesystem.metadata_.Get("/gpu0/incoming"),1)==1);
  }
  static void burst_first_read(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=true;
    cfg.measured_burst_reuse=true;cfg.checksum="fnv1a64";cfg.speculative_copy_may_evict=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",1024,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    for(int k=0;k<10;++k)for(int j=0;j<4;++j)filesystem.measured_.Observe(0,"learn"+std::to_string(k),filesystem.MeasuredOptions());
    auto remote=root/"remote/gpu0/new";std::ofstream(remote)<<std::string(1024,'b');
    FileMeta meta;meta.logical_path="/gpu0/new";meta.gpu_id=0;meta.tier="remote";
    meta.backend_id="remote";meta.physical_path=remote;meta.size_bytes=1024;meta.has_remote_copy=true;meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    filesystem.measured_.Observe(0,meta.logical_path,filesystem.MeasuredOptions());
    filesystem.PlaceShared(meta.logical_path,0);
    assert(filesystem.metadata_.Get(meta.logical_path)->tier=="local");
    assert(fs::file_size(root/"local/new")==1024 && fs::file_size(remote)==1024);
    auto invalid=cfg;invalid.measured_cost=false;bool rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
  }
  static void compact_plan_invariants(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.measured_policy=true;cfg.measured_causal_window=true;
    cfg.measured_cost=false;cfg.compact_measured_planning=true;cfg.lean_read_accounting=true;
    cfg.affinity_placement=false;cfg.speculative_copy_may_evict=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",200,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    for(const auto& key:{"a","b","new"}) {
      const auto bytes=std::string(key)=="new"?200:100;
      auto remote=root/"remote/gpu0"/key;std::ofstream(remote)<<std::string(bytes,key[0]);
      FileMeta meta;meta.logical_path=std::string("/gpu0/")+key;meta.gpu_id=0;
      meta.tier=std::string(key)=="new"?"remote":"local";meta.backend_id=meta.tier;
      meta.physical_path=meta.tier=="local"?root/"local"/key:remote;
      if(meta.tier=="local")fs::copy_file(remote,meta.physical_path);
      meta.size_bytes=bytes;meta.has_remote_copy=true;filesystem.metadata_.Upsert(meta);
      for(int i=0;i<(std::string(key)=="new"?10:2);++i) {
        filesystem.measured_.Observe(0,meta.logical_path,filesystem.MeasuredOptions(),true);
        filesystem.metadata_.IncrementReadCount(meta.logical_path,0,70,55,2,10,3,4,2,3,false);
      }
    }
    auto incoming=*filesystem.metadata_.Get("/gpu0/new");
    const auto compact=filesystem.MeasuredPlan(cfg.gpus[0],incoming);
    filesystem.config_.compact_measured_planning=false;
    const auto reference=filesystem.MeasuredPlan(cfg.gpus[0],incoming);
    assert(compact.allowed && compact.victims.size()==2 && compact.victims==reference.victims);
    assert(compact.displaced_us==reference.displaced_us && compact.incoming_us==reference.incoming_us);
    filesystem.config_.compact_measured_planning=true;
    Handle pin;pin.logical_path="/gpu0/a";
    const auto id=filesystem.StoreHandle(pin);
    assert(!filesystem.MeasuredPlan(cfg.gpus[0],incoming).allowed);
    fuse_file_info fi{};fi.fh=id;filesystem.Release("/gpu0/a",&fi);
    assert(filesystem.EnsureLocalCapacity(cfg.gpus[0],200,"/gpu0/new"));
    assert(TokenFS::DirectoryBytes(root/"local")==0);
    assert(filesystem.metadata_.Get("/gpu0/a")->tier=="remote");
    assert(filesystem.metadata_.Get("/gpu0/b")->tier=="remote");
    assert(fs::file_size(root/"remote/gpu0/a")==100 && fs::file_size(root/"remote/gpu0/b")==100);
    // A persisted replica touch belongs to the same read-count transaction.
    LocalReplica replica;replica.logical_path="/gpu0/a";replica.gpu_id=1;
    replica.physical_path=root/"unconfigured";replica.last_access_at=0;
    filesystem.metadata_.UpsertLocalReplica(replica);
    const auto previous=filesystem.metadata_.Get("/gpu0/a")->read_count;
    assert(filesystem.metadata_.IncrementReadCount("/gpu0/a",1,70,55,2,10,3,4,2,3,false,1)==previous+1);
    assert(filesystem.metadata_.GetLocalReplica("/gpu0/a",1)->last_access_at>0);
    // Stale paths and unconfigured locations cannot contribute shared coverage.
    assert(filesystem.SnapshotMeasuredResidents("").empty());
    auto invalid=cfg;invalid.readonly_canonical=false;
    bool rejected=false;try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
    invalid=cfg;invalid.affinity_placement=true;rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
  }
  static void stale_advisory_plan(const fs::path& root,bool joint=true) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=true;
    cfg.measured_burst_reuse=true;cfg.adaptive_reuse_control=true;cfg.speculative_copy_may_evict=true;
    cfg.measured_joint_admission=joint;
    cfg.gpus.push_back({0,"/gpu0",root/"local",100,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    auto remote=root/"remote/gpu0/new";std::ofstream(remote)<<std::string(100,'x');
    FileMeta meta;meta.logical_path="/gpu0/new";meta.gpu_id=0;meta.tier="remote";meta.backend_id="remote";
    meta.physical_path=remote;meta.size_bytes=100;meta.has_remote_copy=true;meta.state="COMMITTED";filesystem.metadata_.Upsert(meta);
    filesystem.measured_.Observe(0,meta.logical_path,filesystem.MeasuredOptions());
    auto plan=filesystem.MeasuredPlan(cfg.gpus[0],meta);
    assert(plan.allowed && plan.explore_headroom);
    // New untracked bytes arrive between advisory selection and execution.
    std::ofstream(root/"local/unknown")<<std::string(100,'z');
    assert(!filesystem.EnsureLocalCapacity(cfg.gpus[0],100,meta.logical_path));
    assert(fs::file_size(root/"local/unknown")==100 && fs::file_size(remote)==100);
    auto invalid=cfg;invalid.compact_measured_planning=false;bool rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
  }
  static void readable_peer(const fs::path& root) {
    Config cfg; cfg.mount_point=root/"mnt";cfg.metadata_db=root/"peer.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local0",2048,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"local1",2048,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    LocalReplica replica;replica.logical_path="/gpu0/a";replica.gpu_id=1;
    replica.physical_path=root/"local1"/"a";replica.size_bytes=4;
    replica.state="COPYING";std::ofstream(replica.physical_path)<<"data";
    filesystem.metadata_.UpsertLocalReplica(replica);
    assert(!filesystem.ReadablePeer("/gpu0/a",0));
    replica.state="READY";filesystem.metadata_.UpsertLocalReplica(replica);
    assert(filesystem.ReadablePeer("/gpu0/a",0));
    assert(!filesystem.ReadablePeer("/gpu0/a",1));
    int fd=open(filesystem.ReadablePeer("/gpu0/a",0)->physical_path.c_str(),O_RDONLY);
    assert(fd>=0);fs::remove(replica.physical_path);
    assert(!filesystem.ReadablePeer("/gpu0/a",0));
    char bytes[4];assert(pread(fd,bytes,4,0)==4 && std::string(bytes,4)=="data");close(fd);
    cfg.private_cache_domains=true;
    bool rejected=false;try {TokenFS invalid(cfg);invalid.Init();} catch(const std::runtime_error&) {rejected=true;}
    assert(rejected);
    cfg.private_cache_domains=false;cfg.readonly_canonical=false;
    rejected=false;try {TokenFS invalid(cfg);invalid.Init();} catch(const std::runtime_error&) {rejected=true;}
    assert(rejected);
  }
  static void sieve_verified_residents(const fs::path& root) {
    Config cfg; cfg.mount_point=root/"mnt";cfg.metadata_db=root/"sieve.db";
    cfg.local_eviction_policy="sieve";cfg.checksum="fnv1a64";cfg.readonly_canonical=true;cfg.speculative_copy_may_evict=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local0",2048,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"local1",2048,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    for(const auto& key:{"a","b","c"}) {
      auto remote=root/"remote"/"gpu0"/key;
      std::ofstream(remote)<<std::string(1024,key[0]);
      FileMeta meta;meta.logical_path=std::string("/gpu0/")+key;meta.gpu_id=0;
      meta.tier="remote";meta.physical_path=remote;meta.backend_id="remote";
      meta.size_bytes=1024;meta.has_remote_copy=true;meta.state="COMMITTED";
      filesystem.metadata_.Upsert(meta);
      if(std::string(key)=="c")filesystem.sieve_.Hit(0,"/gpu0/a");
      assert(filesystem.PromoteToLocal(cfg.gpus[0],key,meta,"promote")==0);
      filesystem.CreateCrossGpuReplica(cfg.gpus[1],cfg.gpus[0],key,meta);
    }
    assert(filesystem.metadata_.Get("/gpu0/a")->tier=="local");
    assert(filesystem.metadata_.Get("/gpu0/b")->tier=="remote");
    assert(filesystem.metadata_.Get("/gpu0/c")->tier=="local");
    assert(!filesystem.metadata_.GetLocalReplica("/gpu0/a",1));
    assert(filesystem.metadata_.GetLocalReplica("/gpu0/b",1));
    assert(filesystem.metadata_.GetLocalReplica("/gpu0/c",1));
    assert(TokenFS::DirectoryBytes(root/"local0")==2048 && TokenFS::DirectoryBytes(root/"local1")==2048);
    for(const auto& key:{"a","b","c"})assert(fs::file_size(root/"remote"/"gpu0"/key)==1024);
  }
  static void signed_eviction_audit_score() {
    EvictionCandidate candidate;
    candidate.meta.size_bytes=4*1024*1024;
    candidate.meta.read_count=5;
    candidate.meta.recompute_cost=10;
    candidate.meta.remote_access_cost=10;
    candidate.meta.producer_gpu=0;candidate.meta.gpu_id=0;
    candidate.last_access_at=123;
    const auto decision_score=TokenFS::ValueAwareEvictionScore(candidate,0);
    assert(decision_score<0);
    assert(TokenFS::EvictionAuditScore("value_aware",candidate,0)==static_cast<double>(decision_score));
    assert(TokenFS::EvictionAuditScore("lru",candidate,0)==123.0);
    assert(TokenFS::EvictionAuditScore("lfu",candidate,0)==5.0);
  }
  static void lookup_during_eviction(const fs::path& root) {
    Config cfg; cfg.mount_point=root/"mnt";cfg.metadata_db=root/"lookup.db";
    cfg.gpus.push_back({0,"/gpu0",root/"local",4096,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    const auto local=root/"local"/"k";
    const auto remote=root/"remote"/"gpu0"/"k";
    std::ofstream(local)<<"payload";std::ofstream(remote)<<"payload";
    FileMeta meta;meta.logical_path="/gpu0/k";meta.gpu_id=0;meta.tier="local";
    meta.physical_path=local;meta.has_remote_copy=true;meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    std::unique_lock<std::mutex> eviction(filesystem.layout_mu_);
    fs::remove(local);  // Deterministically hold the unlink -> metadata window open.
    std::promise<void> entered;
    auto lookup=std::async(std::launch::async,[&]{
      entered.set_value();struct stat attributes{};
      return filesystem.GetAttr("/gpu0/k",&attributes,nullptr);
    });
    entered.get_future().wait();
    assert(lookup.wait_for(std::chrono::milliseconds(100))==std::future_status::timeout);
    meta.tier="remote";meta.physical_path=remote;filesystem.metadata_.Upsert(meta);
    eviction.unlock();
    assert(lookup.wait_for(std::chrono::seconds(2))==std::future_status::ready);
    assert(lookup.get()==0);
  }
};
}

void MetricBatchTransactions(const fs::path& path) {
  MetadataStore store(path);store.Open();sqlite3* db=nullptr;assert(sqlite3_open(path.c_str(),&db)==SQLITE_OK);
  auto exec=[&](const char* sql){assert(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK);};
  auto values=[&]{std::map<std::string,uint64_t> out;sqlite3_stmt* stmt=nullptr;
    assert(sqlite3_prepare_v2(db,"SELECT name,value FROM metrics",-1,&stmt,nullptr)==SQLITE_OK);
    while(sqlite3_step(stmt)==SQLITE_ROW)out[reinterpret_cast<const char*>(sqlite3_column_text(stmt,0))]=sqlite3_column_int64(stmt,1);
    sqlite3_finalize(stmt);return out;};
  store.ApplyMetricBatch({{"a",2},{"b",3}},{{"a",7},{"peak",4}});
  store.ApplyMetricBatch({{"a",2},{"b",5}},{{"a",6},{"peak",2}});
  store.ApplyMetricBatch({},{});
  const auto before=values();assert(before.at("a")==9 && before.at("b")==8 && before.at("peak")==4);
  exec("CREATE TRIGGER reject_max BEFORE INSERT ON metrics WHEN NEW.name='reject' BEGIN SELECT RAISE(ABORT,'injected failure'); END;");
  bool rejected=false;try {store.ApplyMetricBatch({{"a",100},{"new",99}},{{"reject",1}});}catch(const std::runtime_error&){rejected=true;}
  assert(rejected && values()==before); // Delta work must roll back with a later maximum failure.
  exec("DROP TRIGGER reject_max;");store.ApplyMetricBatch({{"a",1}},{{"peak",8}});
  assert(values().at("a")==10 && values().at("peak")==8);sqlite3_close(db);
}

void ReusedQueriesAndAtomicReplica(const fs::path& path) {
  MetadataStore store(path);store.Open();sqlite3* db=nullptr;assert(sqlite3_open(path.c_str(),&db)==SQLITE_OK);
  auto exec=[&](const char* sql){assert(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK);};
  assert(!store.Get("/gpu0/k") && !store.GetLocalReplica("/gpu0/k",1));
  assert(store.LocalReplicas("/gpu0/k").empty());
  FileMeta f;f.logical_path="/gpu0/k";f.gpu_id=0;f.tier="remote";f.physical_path="/remote/k";f.has_remote_copy=true;f.state="COMMITTED";store.Upsert(f);
  assert(store.Get(f.logical_path)->tier=="remote");
  // A schema invalidation must recompile the query, not keep stale results.
  exec("CREATE INDEX query_test ON files(tier);");
  f.size_bytes=17;store.Upsert(f);assert(store.Get(f.logical_path)->size_bytes==17);
  LocalReplica replica;replica.logical_path=f.logical_path;replica.gpu_id=1;replica.physical_path="/local/k";replica.state="READY";replica.size_bytes=4096;
  exec("CREATE TRIGGER reject_promotion BEFORE UPDATE OF last_promoted_at ON files BEGIN SELECT RAISE(ABORT,'injected'); END;");
  bool rejected=false;try{store.UpsertLocalReplica(replica,true);}catch(const std::runtime_error&){rejected=true;}
  assert(rejected && !store.GetLocalReplica(f.logical_path,1) && store.LocalReplicas(f.logical_path).empty());
  exec("DROP TRIGGER reject_promotion;");store.UpsertLocalReplica(replica,true);
  assert(store.GetLocalReplica(f.logical_path,1)->size_bytes==4096);
  assert(store.LocalReplicas(f.logical_path).size()==1 && store.Get(f.logical_path)->target_local_replica_count>=1);
  std::vector<std::future<void>> readers;
  for(int i=0;i<4;++i)readers.push_back(std::async(std::launch::async,[&]{for(int j=0;j<50;++j){assert(store.Get(f.logical_path)->size_bytes==17);assert(store.GetLocalReplica(f.logical_path,1)->state=="READY");assert(store.LocalReplicas(f.logical_path).size()==1);}}));
  for(auto& reader:readers)reader.get();
  store.RemoveLocalReplica(f.logical_path,1);assert(!store.GetLocalReplica(f.logical_path,1) && store.LocalReplicas(f.logical_path).empty());
  store.Remove(f.logical_path);assert(!store.Get(f.logical_path));
  rejected=false;try{store.UpsertLocalReplica(replica,true);}catch(const std::runtime_error&){rejected=true;}
  assert(rejected && store.LocalReplicas(f.logical_path).empty());sqlite3_close(db);
}

void CachedAccountingRollback(const fs::path& path) {
  {
    MetadataStore store(path);store.Open();FileMeta f;f.logical_path="/gpu0/k";f.gpu_id=0;f.state="COMMITTED";store.Upsert(f);
    auto record=[&](int gpu){return store.IncrementReadCount(f.logical_path,gpu,70,55,2,10,3,4,2,3,false,1);};
    assert(record(0)==1);
    sqlite3* db=nullptr;assert(sqlite3_open(path.c_str(),&db)==SQLITE_OK);
    assert(sqlite3_exec(db,"CREATE TRIGGER reject_access BEFORE INSERT ON gpu_access BEGIN SELECT RAISE(ABORT,'injected'); END;",nullptr,nullptr,nullptr)==SQLITE_OK);
    bool failed=false;try{record(1);}catch(const std::runtime_error&){failed=true;}
    assert(failed && store.Get(f.logical_path)->read_count==1);
    assert(sqlite3_exec(db,"DROP TRIGGER reject_access;",nullptr,nullptr,nullptr)==SQLITE_OK);
    assert(record(1)==2);sqlite3_close(db);
    std::vector<std::future<void>> workers;
    for(int i=0;i<4;++i)workers.push_back(std::async(std::launch::async,[&,i]{for(int j=0;j<50;++j)record(i%3);}));
    for(auto& worker:workers)worker.get();
    assert(store.Get(f.logical_path)->read_count==202 && store.Get(f.logical_path)->share_count==3);
  }
  MetadataStore reopened(path);reopened.Open();assert(reopened.Get("/gpu0/k")->read_count==202);
}

void AtomicFirstRead(const fs::path& path) {
  {
    MetadataStore store(path);store.Open();FileMeta f;
    f.logical_path="/gpu0/new";f.gpu_id=0;f.state="COMMITTED";f.tier="remote";
    f.physical_path="/remote/new";f.has_remote_copy=true;f.size_bytes=4096;
    auto record=[&](const FileMeta* initial){return store.IncrementReadCount(f.logical_path,1,70,55,2,10,3,4,2,3,false,-1,initial);};
    sqlite3* db=nullptr;assert(sqlite3_open(path.c_str(),&db)==SQLITE_OK);
    assert(sqlite3_exec(db,"CREATE TRIGGER reject_first_access BEFORE INSERT ON gpu_access BEGIN SELECT RAISE(ABORT,'injected'); END;",nullptr,nullptr,nullptr)==SQLITE_OK);
    bool failed=false;try{record(&f);}catch(const std::runtime_error&){failed=true;}
    assert(failed && !store.Get(f.logical_path));
    assert(sqlite3_exec(db,"DROP TRIGGER reject_first_access;",nullptr,nullptr,nullptr)==SQLITE_OK);
    assert(record(&f)==1);
    auto actual=store.Get(f.logical_path);assert(actual && actual->read_count==1 && actual->size_bytes==4096 && actual->has_remote_copy);
    // A stale discovery cannot overwrite a newer layout or reset its counts.
    f.physical_path="/wrong";failed=false;
    try{record(&f);}catch(const std::runtime_error&){failed=true;}
    assert(failed && store.Get(f.logical_path)->physical_path=="/remote/new");
    assert(record(nullptr)==2);sqlite3_close(db);
  }
  MetadataStore reopened(path);reopened.Open();
  assert(reopened.Get("/gpu0/new")->read_count==2);
}

int main() {
  const fs::path root = fs::temp_directory_path() / ("tokenfs-policy-test-" + std::to_string(getpid()));
  fs::create_directory(root);
  MetricBatchTransactions(root/"metric-batches.db");
  CachedAccountingRollback(root/"cached-accounting.db");
  AtomicFirstRead(root/"atomic-first-read.db");
  ReusedQueriesAndAtomicReplica(root/"query-reuse.db");
  TokenFSTestAccess::aligned_tail_reads(root/"aligned-tail-enabled",true);
  TokenFSTestAccess::aligned_tail_reads(root/"aligned-tail-disabled",false);
  TokenFSTestAccess::ram_first_routing(root/"ram-first-lean",true,true);
  TokenFSTestAccess::ram_first_routing(root/"ram-first-legacy",true,false);
  TokenFSTestAccess::ram_first_routing(root/"ram-last-lean",false,true);
  TokenFSTestAccess::ram_first_routing(root/"ram-last-legacy",false,false);
  TokenFSTestAccess::sieve_ram_permissions(root/"sieve-ram-permissions");
  TokenFSTestAccess::telemetry_retry_and_release_lock(root/"telemetry-retry");
  TokenFSTestAccess::background_metric_fence(root/"metric-fence-on",true);
  TokenFSTestAccess::background_metric_fence(root/"metric-fence-off",false);
  TokenFSTestAccess::deferred_background_fence(root/"deferred-fence");
  TokenFSTestAccess::deferred_config_parse(root/"deferred-config");
  for(int retry_mode=0;retry_mode<3;++retry_mode)
    TokenFSTestAccess::deferred_background_failure_retry(root/("deferred-retry-"+std::to_string(retry_mode)),retry_mode);
  TokenFSTestAccess::deferred_background_queue_shutdown(root/"deferred-queue-shutdown");
  TokenFSTestAccess::deferred_failed_fence_handoff(root/"deferred-failed-handoff");
  TokenFSTestAccess::readonly_release_fence(root/"readonly-release-fence");
  TokenFSTestAccess::submission_precheck_decisions(root/"precheck-decisions");
  TokenFSTestAccess::submission_precheck_ablations(root/"precheck-ablations");
  TokenFSTestAccess::submission_precheck_busy(root/"precheck-busy");
  TokenFSTestAccess::submission_precheck_metadata(root/"precheck-metadata");
  TokenFSTestAccess::submission_precheck_startup(root/"precheck-startup");
  TokenFSTestAccess::inflight_reads(root/"inflight-enabled",true);
  TokenFSTestAccess::inflight_reads(root/"inflight-disabled",false);
  TokenFSTestAccess::inflight_reads(root/"retained-after-ready",true,true);
  TokenFSTestAccess::retained_rejected(root/"retained-rejected");
  TokenFSTestAccess::foreground_fill(root/"fill-sieve1",1);
  TokenFSTestAccess::foreground_fill(root/"fill-sieve2",2);
  TokenFSTestAccess::foreground_fill(root/"fill-adaptive",1,true);
  TokenFSTestAccess::foreground_fill(root/"fill-incremental",1,true,true);
  TokenFSTestAccess::request_trace_roundtrip(root/"request-trace");
  TokenFSTestAccess::burst_first_read(root/"burst-first-read");
  auto observe = [](MetadataStore& db, const std::string& key, int gpu) {
    return db.IncrementReadCount(key, gpu, 70, 55, 2, 10, 3, 4, 2, 3);
  };
  {
    MetadataStore db(root / "meta.db"); db.Open();
    for (const auto& key : {"/gpu0/a", "/gpu0/b"}) {
      FileMeta meta; meta.logical_path=key; meta.gpu_id=0; meta.tier="local";
      meta.backend_id="local"; meta.physical_path=root / fs::path(key).filename();
      meta.size_bytes=1024; meta.has_remote_copy=true; db.Upsert(meta);
    }
    observe(db,"/gpu0/a",0); observe(db,"/gpu0/b",0); observe(db,"/gpu0/a",0);
    auto candidates=db.LocalEvictionCandidates(0, "");
    assert(candidates.size()==2);
    auto a=std::find_if(candidates.begin(), candidates.end(), [](const auto& c){ return c.meta.logical_path=="/gpu0/a"; });
    auto b=std::find_if(candidates.begin(), candidates.end(), [](const auto& c){ return c.meta.logical_path=="/gpu0/b"; });
    assert(a->last_access_at>b->last_access_at);
    assert(a->meta.read_count==2 && b->meta.read_count==1);
    LocalReplica replica; replica.logical_path="/gpu0/a"; replica.gpu_id=1;
    replica.physical_path=root / "replica"; replica.size_bytes=1024; db.UpsertLocalReplica(replica);
    observe(db,"/gpu0/a",1);
    auto cross=db.LocalEvictionCandidates(1, "");
    assert(cross.size()==1 && cross[0].replica_gpu==1 && cross[0].meta.read_count==1);
  }
  {
    MetadataStore db(root / "meta.db"); db.Open();
    observe(db,"/gpu0/b",0);
    auto candidates=db.LocalEvictionCandidates(0, "");
    auto newest=std::max_element(candidates.begin(), candidates.end(), [](const auto& a,const auto& b){return a.last_access_at<b.last_access_at;});
    assert(newest->meta.logical_path=="/gpu0/b");
  }
  TokenFSTestAccess::lookup_during_eviction(root/"lookup-race");
  TokenFSTestAccess::readable_peer(root/"peer-storage");
  TokenFSTestAccess::shared_placement(root/"caller-only-placement",true,false,true);
  TokenFSTestAccess::shared_placement(root/"shared-placement");
  TokenFSTestAccess::stale_advisory_plan(root/"independent-stale-plan",false);
  TokenFSTestAccess::shared_placement(root/"compact-shared-placement",true);
  TokenFSTestAccess::shared_placement(root/"adaptive-shared-placement",true,true);
  TokenFSTestAccess::compact_plan_invariants(root/"compact-invariants");
  TokenFSTestAccess::stale_advisory_plan(root/"stale-advisory");
  TokenFSTestAccess::signed_eviction_audit_score();
  TokenFSTestAccess::sieve_verified_residents(root/"sieve-storage");
  fs::remove_all(root);
  std::cout << "policy metadata invariants passed\n";
}
