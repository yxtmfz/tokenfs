// Exercise the real metadata implementation, including access ordering within one second.
#define main tokenfs_daemon_entry_for_test
#include "../src/main.cpp"
#undef main
#include <cassert>
#include <future>

namespace {
struct TokenFSTestAccess {
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
  TokenFSTestAccess::signed_eviction_audit_score();
  fs::remove_all(root);
  std::cout << "policy metadata invariants passed\n";
}
