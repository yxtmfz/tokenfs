// Exercise the real metadata implementation, including access ordering within one second.
#define main tokenfs_daemon_entry_for_test
#include "../src/main.cpp"
#undef main
#include <cassert>
#include <future>

namespace {
struct TokenFSTestAccess {
  static void shared_placement(const fs::path& root,bool compact=false,bool adaptive=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=compact;cfg.measured_cost=false;cfg.checksum="fnv1a64";
    cfg.speculative_copy_may_evict=true;
    cfg.adaptive_reuse_control=adaptive;cfg.measured_burst_reuse=adaptive;cfg.measured_cost=adaptive;
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
  static void stale_advisory_plan(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=true;
    cfg.measured_burst_reuse=true;cfg.adaptive_reuse_control=true;cfg.speculative_copy_may_evict=true;
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
    auto invalid=cfg;invalid.measured_joint_admission=false;bool rejected=false;
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

int main() {
  const fs::path root = fs::temp_directory_path() / ("tokenfs-policy-test-" + std::to_string(getpid()));
  fs::create_directory(root);
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
  TokenFSTestAccess::shared_placement(root/"shared-placement");
  TokenFSTestAccess::shared_placement(root/"compact-shared-placement",true);
  TokenFSTestAccess::shared_placement(root/"adaptive-shared-placement",true,true);
  TokenFSTestAccess::compact_plan_invariants(root/"compact-invariants");
  TokenFSTestAccess::stale_advisory_plan(root/"stale-advisory");
  TokenFSTestAccess::signed_eviction_audit_score();
  TokenFSTestAccess::sieve_verified_residents(root/"sieve-storage");
  fs::remove_all(root);
  std::cout << "policy metadata invariants passed\n";
}
