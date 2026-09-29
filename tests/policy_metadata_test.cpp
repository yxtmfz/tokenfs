// Exercise the real metadata implementation, including access ordering within one second.
#define main tokenfs_daemon_entry_for_test
#include "../src/main.cpp"
#undef main
#include <cassert>
#include <future>
#include <map>

namespace {
struct TokenFSTestAccess {
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
  static void inflight_reads(const fs::path& root,bool enabled,bool retained=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=enabled;cfg.retain_read_fill=retained;cfg.batch_background_metrics=true;
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

int main() {
  const fs::path root = fs::temp_directory_path() / ("tokenfs-policy-test-" + std::to_string(getpid()));
  fs::create_directory(root);
  MetricBatchTransactions(root/"metric-batches.db");
  TokenFSTestAccess::background_metric_fence(root/"metric-fence-on",true);
  TokenFSTestAccess::background_metric_fence(root/"metric-fence-off",false);
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
