#define FUSE_USE_VERSION 35

#include <fuse3/fuse.h>
#include <sqlite3.h>
#include <yaml-cpp/yaml.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace fs = std::filesystem;

namespace {

struct BackendConfig {
  std::string id;
  std::string type;
  fs::path root;
};

struct GpuConfig {
  int gpu_id = -1;
  std::string logical_root;
  fs::path local_root;
  uint64_t local_quota_bytes = 0;
  std::string remote_backend;
};

struct Config {
  fs::path mount_point;
  fs::path metadata_db;
  std::string temp_suffix = ".tokenfs_tmp";
  std::string checksum = "none";
  std::string local_eviction_policy = "value_aware";
  std::string placement_policy = "value_aware";
  uint64_t default_recompute_cost = 10;
  uint64_t default_remote_access_cost = 10;
  uint64_t value_promote_threshold = 100;
  bool adaptive_migration = false;
  uint64_t adaptive_remote_promote_us = 10000;
  uint64_t qos_read_iops_per_gpu = 0;
  uint64_t qos_write_iops_per_gpu = 0;
  uint64_t qos_background_iops_per_gpu = 0;
  uint64_t qos_background_mib_per_sec_per_gpu = 0;
  uint64_t affinity_dominant_threshold_x100 = 70;
  uint64_t affinity_shared_threshold_x100 = 55;
  uint64_t affinity_short_window_sec = 300;
  uint64_t affinity_long_window_sec = 3600;
  uint64_t affinity_trend_min_reads = 3;
  uint64_t affinity_hot_read_threshold = 4;
  uint64_t affinity_warm_read_threshold = 2;
  uint64_t max_local_replicas_per_file = 2;
  uint64_t affinity_replica_cooldown_sec = 30;
  uint64_t affinity_replica_min_residency_sec = 120;
  bool cross_gpu_local_cache = false;
  bool physical_dedup = false;
  bool promote_on_read = false;
  uint64_t promote_read_threshold = 2;
  bool prefetch_on_read = false;
  std::unordered_map<std::string, BackendConfig> backends;
  std::vector<GpuConfig> gpus;
};

struct FileMeta {
  std::string logical_path;
  int gpu_id = -1;
  std::string tier;
  std::string backend_id;
  fs::path physical_path;
  uint64_t size_bytes = 0;
  std::string checksum;
  std::string state = "COMMITTED";
  uint64_t read_count = 0;
  std::string content_key;
  uint64_t recompute_cost = 10;
  uint64_t remote_access_cost = 10;
  uint64_t producer_gpu = 0;
  uint64_t share_count = 1;
  std::string primary_tier = "local";
  bool has_remote_copy = false;
  int local_cache_owner_gpu = -1;
  std::string replica_state = "LOCAL_ONLY";
  uint64_t cache_generation = 0;
  uint64_t last_promoted_at = 0;
  uint64_t last_demoted_at = 0;
  int dominant_gpu_id = -1;
  uint64_t dominant_gpu_read_share_x100 = 0;
  int recent_dominant_gpu_id = -1;
  uint64_t recent_dominant_gpu_read_share_x100 = 0;
  uint64_t recent_read_count = 0;
  std::string affinity_trend = "STABLE";
  uint64_t target_local_replica_count = 0;
  std::string affinity_state = "UNKNOWN";
  uint64_t affinity_updated_at = 0;
};

struct ContentRefResult {
  bool duplicate = false;
  uint64_t ref_count = 0;
  std::string primary_logical_path;
  fs::path primary_physical_path;
};

struct EvictionCandidate {
  FileMeta meta;
  uint64_t last_access_at = 0;
};

struct LocalReplica {
  std::string logical_path;
  int gpu_id = -1;
  fs::path physical_path;
  uint64_t size_bytes = 0;
  uint64_t cache_generation = 0;
  uint64_t created_at = 0;
  uint64_t last_access_at = 0;
  std::string state = "READY";
};

struct Handle {
  int fd = -1;
  std::string logical_path;
  int gpu_id = -1;
  int caller_gpu_id = -1;
  std::string tier;
  std::string backend_id;
  fs::path physical_path;
  int flags = 0;
  bool writable = false;
  bool created_remote = false;
  std::string state = "COMMITTED";
  std::string last_checksum;
  bool pending_physical_dedup = false;
  fs::path dedup_primary_path;
};

class MetadataStore {
 public:
  explicit MetadataStore(const fs::path& db_path) : db_path_(db_path) {}

  ~MetadataStore() {
    if (db_ != nullptr) {
      sqlite3_close(db_);
    }
  }

  void Open() {
    fs::create_directories(db_path_.parent_path());
    if (sqlite3_open(db_path_.c_str(), &db_) != SQLITE_OK) {
      throw std::runtime_error(sqlite3_errmsg(db_));
    }
    Exec("PRAGMA journal_mode=WAL;");
    Exec("PRAGMA synchronous=FULL;");
    Exec("CREATE TABLE IF NOT EXISTS files ("
         "logical_path TEXT PRIMARY KEY,"
         "gpu_id INTEGER NOT NULL,"
         "tier TEXT NOT NULL,"
         "backend_id TEXT NOT NULL,"
         "physical_path TEXT NOT NULL,"
         "size_bytes INTEGER NOT NULL DEFAULT 0,"
         "checksum TEXT,"
         "state TEXT NOT NULL,"
         "created_at INTEGER NOT NULL,"
         "updated_at INTEGER NOT NULL,"
         "last_access_at INTEGER,"
         "read_count INTEGER NOT NULL DEFAULT 0,"
         "content_key TEXT,"
         "recompute_cost INTEGER NOT NULL DEFAULT 10,"
         "remote_access_cost INTEGER NOT NULL DEFAULT 10,"
         "producer_gpu INTEGER NOT NULL DEFAULT 0,"
         "share_count INTEGER NOT NULL DEFAULT 1,"
         "primary_tier TEXT NOT NULL DEFAULT 'local',"
         "has_remote_copy INTEGER NOT NULL DEFAULT 0,"
         "local_cache_owner_gpu INTEGER NOT NULL DEFAULT -1,"
         "replica_state TEXT NOT NULL DEFAULT 'LOCAL_ONLY',"
         "cache_generation INTEGER NOT NULL DEFAULT 0,"
         "last_promoted_at INTEGER NOT NULL DEFAULT 0,"
         "last_demoted_at INTEGER NOT NULL DEFAULT 0,"
         "dominant_gpu_id INTEGER NOT NULL DEFAULT -1,"
         "dominant_gpu_read_share_x100 INTEGER NOT NULL DEFAULT 0,"
         "recent_dominant_gpu_id INTEGER NOT NULL DEFAULT -1,"
         "recent_dominant_gpu_read_share_x100 INTEGER NOT NULL DEFAULT 0,"
         "recent_read_count INTEGER NOT NULL DEFAULT 0,"
         "affinity_trend TEXT NOT NULL DEFAULT 'STABLE',"
         "target_local_replica_count INTEGER NOT NULL DEFAULT 0,"
         "affinity_state TEXT NOT NULL DEFAULT 'UNKNOWN',"
         "affinity_updated_at INTEGER NOT NULL DEFAULT 0"
         ");");
    EnsureColumn("files", "checksum", "TEXT");
    EnsureColumn("files", "read_count", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "content_key", "TEXT");
    EnsureColumn("files", "recompute_cost", "INTEGER NOT NULL DEFAULT 10");
    EnsureColumn("files", "remote_access_cost", "INTEGER NOT NULL DEFAULT 10");
    EnsureColumn("files", "producer_gpu", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "share_count", "INTEGER NOT NULL DEFAULT 1");
    EnsureColumn("files", "primary_tier", "TEXT NOT NULL DEFAULT 'local'");
    EnsureColumn("files", "has_remote_copy", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "local_cache_owner_gpu",
                 "INTEGER NOT NULL DEFAULT -1");
    EnsureColumn("files", "replica_state",
                 "TEXT NOT NULL DEFAULT 'LOCAL_ONLY'");
    EnsureColumn("files", "cache_generation", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "last_promoted_at", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "last_demoted_at", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "dominant_gpu_id", "INTEGER NOT NULL DEFAULT -1");
    EnsureColumn("files", "dominant_gpu_read_share_x100",
                 "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "recent_dominant_gpu_id",
                 "INTEGER NOT NULL DEFAULT -1");
    EnsureColumn("files", "recent_dominant_gpu_read_share_x100",
                 "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "recent_read_count", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "affinity_trend",
                 "TEXT NOT NULL DEFAULT 'STABLE'");
    EnsureColumn("files", "target_local_replica_count",
                 "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "affinity_state",
                 "TEXT NOT NULL DEFAULT 'UNKNOWN'");
    EnsureColumn("files", "affinity_updated_at", "INTEGER NOT NULL DEFAULT 0");
    Exec("CREATE TABLE IF NOT EXISTS metrics ("
         "name TEXT PRIMARY KEY,"
         "value INTEGER NOT NULL DEFAULT 0"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS gpu_access ("
         "logical_path TEXT NOT NULL,"
         "gpu_id INTEGER NOT NULL,"
         "read_count INTEGER NOT NULL DEFAULT 0,"
         "last_access_at INTEGER,"
         "PRIMARY KEY(logical_path,gpu_id)"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS gpu_access_events ("
         "logical_path TEXT NOT NULL,"
         "gpu_id INTEGER NOT NULL,"
         "access_at INTEGER NOT NULL"
         ");");
    Exec("CREATE INDEX IF NOT EXISTS idx_gpu_access_events_path_time "
         "ON gpu_access_events(logical_path,access_at);");
    Exec("CREATE TABLE IF NOT EXISTS local_replicas ("
         "logical_path TEXT NOT NULL,"
         "gpu_id INTEGER NOT NULL,"
         "physical_path TEXT NOT NULL,"
         "size_bytes INTEGER NOT NULL DEFAULT 0,"
         "cache_generation INTEGER NOT NULL DEFAULT 0,"
         "created_at INTEGER NOT NULL,"
         "last_access_at INTEGER NOT NULL,"
         "state TEXT NOT NULL DEFAULT 'READY',"
         "PRIMARY KEY(logical_path,gpu_id)"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS content_refs ("
         "content_key TEXT PRIMARY KEY,"
         "primary_logical_path TEXT NOT NULL,"
         "physical_path TEXT NOT NULL,"
         "size_bytes INTEGER NOT NULL DEFAULT 0,"
         "ref_count INTEGER NOT NULL DEFAULT 0,"
         "first_seen_at INTEGER NOT NULL,"
         "last_seen_at INTEGER NOT NULL"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS content_members ("
         "content_key TEXT NOT NULL,"
         "logical_path TEXT NOT NULL,"
         "PRIMARY KEY(content_key,logical_path)"
         ");");
  }

  std::optional<FileMeta> Get(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    const char* sql =
        "SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
        "COALESCE(checksum,''),state,COALESCE(read_count,0),"
        "COALESCE(content_key,''),COALESCE(recompute_cost,10),"
        "COALESCE(remote_access_cost,10),COALESCE(producer_gpu,0),"
        "COALESCE(share_count,1),COALESCE(primary_tier,'local'),"
        "COALESCE(has_remote_copy,0),COALESCE(local_cache_owner_gpu,-1),"
        "COALESCE(replica_state,'LOCAL_ONLY'),COALESCE(cache_generation,0),"
        "COALESCE(last_promoted_at,0),COALESCE(last_demoted_at,0),"
        "COALESCE(dominant_gpu_id,-1),"
        "COALESCE(dominant_gpu_read_share_x100,0),"
        "COALESCE(recent_dominant_gpu_id,-1),"
        "COALESCE(recent_dominant_gpu_read_share_x100,0),"
        "COALESCE(recent_read_count,0),"
        "COALESCE(affinity_trend,'STABLE'),"
        "COALESCE(target_local_replica_count,0),"
        "COALESCE(affinity_state,'UNKNOWN'),COALESCE(affinity_updated_at,0) "
        "FROM files WHERE logical_path=?;";
    sqlite3_stmt* stmt = nullptr;
    Prepare(sql, &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
      sqlite3_finalize(stmt);
      return std::nullopt;
    }
    if (rc != SQLITE_ROW) {
      std::string err = sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
      throw std::runtime_error(err);
    }
    FileMeta meta;
    meta.logical_path = ColumnText(stmt, 0);
    meta.gpu_id = sqlite3_column_int(stmt, 1);
    meta.tier = ColumnText(stmt, 2);
    meta.backend_id = ColumnText(stmt, 3);
    meta.physical_path = ColumnText(stmt, 4);
    meta.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
    meta.checksum = ColumnText(stmt, 6);
    meta.state = ColumnText(stmt, 7);
    meta.read_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 8));
    meta.content_key = ColumnText(stmt, 9);
    meta.recompute_cost = static_cast<uint64_t>(sqlite3_column_int64(stmt, 10));
    meta.remote_access_cost =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 11));
    meta.producer_gpu = static_cast<uint64_t>(sqlite3_column_int64(stmt, 12));
    meta.share_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 13));
    meta.primary_tier = ColumnText(stmt, 14);
    meta.has_remote_copy = sqlite3_column_int64(stmt, 15) != 0;
    meta.local_cache_owner_gpu = sqlite3_column_int(stmt, 16);
    meta.replica_state = ColumnText(stmt, 17);
    meta.cache_generation =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 18));
    meta.last_promoted_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 19));
    meta.last_demoted_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 20));
    meta.dominant_gpu_id = sqlite3_column_int(stmt, 21);
    meta.dominant_gpu_read_share_x100 =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 22));
    meta.recent_dominant_gpu_id = sqlite3_column_int(stmt, 23);
    meta.recent_dominant_gpu_read_share_x100 =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 24));
    meta.recent_read_count =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 25));
    meta.affinity_trend = ColumnText(stmt, 26);
    meta.target_local_replica_count =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 27));
    meta.affinity_state = ColumnText(stmt, 28);
    meta.affinity_updated_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 29));
    sqlite3_finalize(stmt);
    return meta;
  }

  void Upsert(const FileMeta& meta) {
    std::lock_guard<std::mutex> lock(mu_);
    const auto now = UnixNow();
    const char* sql =
        "INSERT INTO files(logical_path,gpu_id,tier,backend_id,physical_path,"
        "size_bytes,checksum,state,created_at,updated_at,last_access_at,read_count,"
        "content_key,recompute_cost,remote_access_cost,producer_gpu,share_count,"
        "primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state,"
        "cache_generation,last_promoted_at,last_demoted_at,dominant_gpu_id,"
        "dominant_gpu_read_share_x100,recent_dominant_gpu_id,"
        "recent_dominant_gpu_read_share_x100,recent_read_count,affinity_trend,"
        "target_local_replica_count,affinity_state,affinity_updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(logical_path) DO UPDATE SET "
        "gpu_id=excluded.gpu_id,"
        "tier=excluded.tier,"
        "backend_id=excluded.backend_id,"
        "physical_path=excluded.physical_path,"
        "size_bytes=excluded.size_bytes,"
        "checksum=excluded.checksum,"
        "state=excluded.state,"
        "content_key=excluded.content_key,"
        "recompute_cost=excluded.recompute_cost,"
        "remote_access_cost=excluded.remote_access_cost,"
        "producer_gpu=excluded.producer_gpu,"
        "share_count=excluded.share_count,"
        "primary_tier=excluded.primary_tier,"
        "has_remote_copy=excluded.has_remote_copy,"
        "local_cache_owner_gpu=excluded.local_cache_owner_gpu,"
        "replica_state=excluded.replica_state,"
        "cache_generation=excluded.cache_generation,"
        "last_promoted_at=excluded.last_promoted_at,"
        "last_demoted_at=excluded.last_demoted_at,"
        "dominant_gpu_id=excluded.dominant_gpu_id,"
        "dominant_gpu_read_share_x100=excluded.dominant_gpu_read_share_x100,"
        "recent_dominant_gpu_id=excluded.recent_dominant_gpu_id,"
        "recent_dominant_gpu_read_share_x100=excluded.recent_dominant_gpu_read_share_x100,"
        "recent_read_count=excluded.recent_read_count,"
        "affinity_trend=excluded.affinity_trend,"
        "target_local_replica_count=excluded.target_local_replica_count,"
        "affinity_state=excluded.affinity_state,"
        "affinity_updated_at=excluded.affinity_updated_at,"
        "updated_at=excluded.updated_at;";
    sqlite3_stmt* stmt = nullptr;
    Prepare(sql, &stmt);
    sqlite3_bind_text(stmt, 1, meta.logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, meta.gpu_id);
    sqlite3_bind_text(stmt, 3, meta.tier.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, meta.backend_id.c_str(), -1, SQLITE_TRANSIENT);
    const auto physical = meta.physical_path.string();
    sqlite3_bind_text(stmt, 5, physical.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 6, static_cast<sqlite3_int64>(meta.size_bytes));
    sqlite3_bind_text(stmt, 7, meta.checksum.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 8, meta.state.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 9, now);
    sqlite3_bind_int64(stmt, 10, now);
    sqlite3_bind_int64(stmt, 11, now);
    sqlite3_bind_int64(stmt, 12, static_cast<sqlite3_int64>(meta.read_count));
    sqlite3_bind_text(stmt, 13, meta.content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 14, static_cast<sqlite3_int64>(meta.recompute_cost));
    sqlite3_bind_int64(stmt, 15,
                       static_cast<sqlite3_int64>(meta.remote_access_cost));
    sqlite3_bind_int64(stmt, 16, static_cast<sqlite3_int64>(meta.producer_gpu));
    sqlite3_bind_int64(stmt, 17, static_cast<sqlite3_int64>(meta.share_count));
    sqlite3_bind_text(stmt, 18, meta.primary_tier.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 19, meta.has_remote_copy ? 1 : 0);
    sqlite3_bind_int(stmt, 20, meta.local_cache_owner_gpu);
    sqlite3_bind_text(stmt, 21, meta.replica_state.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 22,
                       static_cast<sqlite3_int64>(meta.cache_generation));
    sqlite3_bind_int64(stmt, 23,
                       static_cast<sqlite3_int64>(meta.last_promoted_at));
    sqlite3_bind_int64(stmt, 24,
                       static_cast<sqlite3_int64>(meta.last_demoted_at));
    sqlite3_bind_int(stmt, 25, meta.dominant_gpu_id);
    sqlite3_bind_int64(
        stmt, 26,
        static_cast<sqlite3_int64>(meta.dominant_gpu_read_share_x100));
    sqlite3_bind_int(stmt, 27, meta.recent_dominant_gpu_id);
    sqlite3_bind_int64(
        stmt, 28,
        static_cast<sqlite3_int64>(meta.recent_dominant_gpu_read_share_x100));
    sqlite3_bind_int64(stmt, 29,
                       static_cast<sqlite3_int64>(meta.recent_read_count));
    sqlite3_bind_text(stmt, 30, meta.affinity_trend.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(
        stmt, 31,
        static_cast<sqlite3_int64>(meta.target_local_replica_count));
    sqlite3_bind_text(stmt, 32, meta.affinity_state.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 33,
                       static_cast<sqlite3_int64>(meta.affinity_updated_at));
    StepDone(stmt);
  }

  uint64_t IncrementReadCount(const std::string& logical_path, int gpu_id,
                              uint64_t dominant_threshold_x100,
                              uint64_t shared_threshold_x100,
                              uint64_t short_window_sec,
                              uint64_t long_window_sec,
                              uint64_t trend_min_reads,
                              uint64_t hot_read_threshold,
                              uint64_t warm_read_threshold,
                              uint64_t max_local_replicas) {
    std::lock_guard<std::mutex> lock(mu_);
    const auto now = UnixNow();
    sqlite3_stmt* stmt = nullptr;
    Prepare("UPDATE files SET read_count=COALESCE(read_count,0)+1,"
            "last_access_at=? WHERE logical_path=?;",
            &stmt);
    sqlite3_bind_int64(stmt, 1, now);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    Prepare("INSERT INTO gpu_access(logical_path,gpu_id,read_count,last_access_at) "
            "VALUES(?,?,1,?) "
            "ON CONFLICT(logical_path,gpu_id) DO UPDATE SET "
            "read_count=read_count+1,last_access_at=excluded.last_access_at;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    sqlite3_bind_int64(stmt, 3, now);
    StepDone(stmt);

    Prepare("INSERT INTO gpu_access_events(logical_path,gpu_id,access_at) "
            "VALUES(?,?,?);",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    sqlite3_bind_int64(stmt, 3, now);
    StepDone(stmt);

    Prepare("DELETE FROM gpu_access_events WHERE logical_path=? AND access_at<?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(
        stmt, 2,
        now - static_cast<sqlite3_int64>(std::max<uint64_t>(long_window_sec, short_window_sec)));
    StepDone(stmt);

    Prepare("UPDATE files SET share_count=("
            "SELECT COUNT(*) FROM gpu_access WHERE logical_path=?) "
            "WHERE logical_path=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    UpdateAffinityLocked(logical_path, dominant_threshold_x100,
                         shared_threshold_x100, short_window_sec,
                         long_window_sec, trend_min_reads,
                         hot_read_threshold, warm_read_threshold,
                         max_local_replicas);

    Prepare("SELECT COALESCE(read_count,0) FROM files WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt);
    if (rc != SQLITE_ROW) {
      std::string err = rc == SQLITE_DONE ? "missing file metadata" : sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
      throw std::runtime_error(err);
    }
    uint64_t count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 0));
    sqlite3_finalize(stmt);
    return count;
  }

  void Remove(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM local_replicas WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM gpu_access WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM gpu_access_events WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM content_members WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM files WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  void AddMetric(const std::string& name, uint64_t delta) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("INSERT INTO metrics(name,value) VALUES(?,?) "
            "ON CONFLICT(name) DO UPDATE SET value=value+excluded.value;",
            &stmt);
    sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(delta));
    StepDone(stmt);
  }

  void SetMetricMax(const std::string& name, uint64_t value) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("INSERT INTO metrics(name,value) VALUES(?,?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "value=CASE WHEN excluded.value > value THEN excluded.value ELSE value END;",
            &stmt);
    sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(value));
    StepDone(stmt);
  }

  uint64_t AccessAffinityX100(const std::string& logical_path, int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT "
            "COALESCE((SELECT read_count FROM gpu_access "
            "          WHERE logical_path=? AND gpu_id=?),0),"
            "COALESCE((SELECT SUM(read_count) FROM gpu_access "
            "          WHERE logical_path=?),0);",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    sqlite3_bind_text(stmt, 3, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    uint64_t affinity = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      uint64_t gpu_reads = static_cast<uint64_t>(sqlite3_column_int64(stmt, 0));
      uint64_t total_reads = static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
      if (total_reads > 0) {
        affinity = std::max<uint64_t>(1, gpu_reads * 100 / total_reads);
      }
    }
    sqlite3_finalize(stmt);
    return affinity;
  }

  std::optional<LocalReplica> GetLocalReplica(const std::string& logical_path,
                                               int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,physical_path,size_bytes,"
            "cache_generation,created_at,last_access_at,state "
            "FROM local_replicas WHERE logical_path=? AND gpu_id=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
      sqlite3_finalize(stmt);
      return std::nullopt;
    }
    if (rc != SQLITE_ROW) {
      std::string err = sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
      throw std::runtime_error(err);
    }
    LocalReplica replica;
    replica.logical_path = ColumnText(stmt, 0);
    replica.gpu_id = sqlite3_column_int(stmt, 1);
    replica.physical_path = ColumnText(stmt, 2);
    replica.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 3));
    replica.cache_generation =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 4));
    replica.created_at = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
    replica.last_access_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 6));
    replica.state = ColumnText(stmt, 7);
    sqlite3_finalize(stmt);
    return replica;
  }

  std::vector<LocalReplica> LocalReplicas(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,physical_path,size_bytes,"
            "cache_generation,created_at,last_access_at,state "
            "FROM local_replicas WHERE logical_path=? "
            "ORDER BY last_access_at ASC,created_at ASC;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    std::vector<LocalReplica> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      LocalReplica replica;
      replica.logical_path = ColumnText(stmt, 0);
      replica.gpu_id = sqlite3_column_int(stmt, 1);
      replica.physical_path = ColumnText(stmt, 2);
      replica.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 3));
      replica.cache_generation =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 4));
      replica.created_at = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      replica.last_access_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 6));
      replica.state = ColumnText(stmt, 7);
      out.push_back(std::move(replica));
    }
    sqlite3_finalize(stmt);
    return out;
  }

  void UpsertLocalReplica(const LocalReplica& replica) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    const auto physical = replica.physical_path.string();
    Prepare("INSERT INTO local_replicas(logical_path,gpu_id,physical_path,"
            "size_bytes,cache_generation,created_at,last_access_at,state) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(logical_path,gpu_id) DO UPDATE SET "
            "physical_path=excluded.physical_path,"
            "size_bytes=excluded.size_bytes,"
            "cache_generation=excluded.cache_generation,"
            "last_access_at=excluded.last_access_at,"
            "state=excluded.state;",
            &stmt);
    sqlite3_bind_text(stmt, 1, replica.logical_path.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, replica.gpu_id);
    sqlite3_bind_text(stmt, 3, physical.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 4, static_cast<sqlite3_int64>(replica.size_bytes));
    sqlite3_bind_int64(
        stmt, 5, static_cast<sqlite3_int64>(replica.cache_generation));
    sqlite3_bind_int64(stmt, 6, static_cast<sqlite3_int64>(replica.created_at));
    sqlite3_bind_int64(stmt, 7,
                       static_cast<sqlite3_int64>(replica.last_access_at));
    sqlite3_bind_text(stmt, 8, replica.state.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  void TouchLocalReplica(const std::string& logical_path, int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("UPDATE local_replicas SET last_access_at=? "
            "WHERE logical_path=? AND gpu_id=?;",
            &stmt);
    sqlite3_bind_int64(stmt, 1, UnixNow());
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 3, gpu_id);
    StepDone(stmt);
  }

  void RemoveLocalReplica(const std::string& logical_path, int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM local_replicas WHERE logical_path=? AND gpu_id=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    StepDone(stmt);
  }

  void RemoveLocalReplicas(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM local_replicas WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  ContentRefResult RegisterContentRef(const std::string& content_key,
                                      const std::string& logical_path,
                                      const fs::path& physical_path,
                                      uint64_t size_bytes) {
    ContentRefResult result;
    if (content_key.empty()) {
      return result;
    }
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT primary_logical_path,physical_path,ref_count "
            "FROM content_refs WHERE content_key=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      result.primary_logical_path = ColumnText(stmt, 0);
      result.primary_physical_path = ColumnText(stmt, 1);
      result.ref_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 2));
    }
    sqlite3_finalize(stmt);

    Prepare("SELECT COUNT(*) FROM content_members "
            "WHERE content_key=? AND logical_path != ?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      result.duplicate = sqlite3_column_int64(stmt, 0) > 0;
    }
    sqlite3_finalize(stmt);

    const auto now = UnixNow();
    const auto physical = physical_path.string();
    Prepare("INSERT OR IGNORE INTO content_refs("
            "content_key,primary_logical_path,physical_path,size_bytes,"
            "ref_count,first_seen_at,last_seen_at) "
            "VALUES(?,?,?,?,0,?,?);",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, physical.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 4, static_cast<sqlite3_int64>(size_bytes));
    sqlite3_bind_int64(stmt, 5, now);
    sqlite3_bind_int64(stmt, 6, now);
    StepDone(stmt);

    Prepare("INSERT OR IGNORE INTO content_members(content_key,logical_path) "
            "VALUES(?,?);",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    Prepare("UPDATE content_refs SET "
            "size_bytes=?,"
            "last_seen_at=?,"
            "ref_count=(SELECT COUNT(*) FROM content_members "
            "           WHERE content_key=?) "
            "WHERE content_key=?;",
            &stmt);
    sqlite3_bind_int64(stmt, 1, static_cast<sqlite3_int64>(size_bytes));
    sqlite3_bind_int64(stmt, 2, now);
    sqlite3_bind_text(stmt, 3, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, content_key.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    Prepare("SELECT primary_logical_path,physical_path,ref_count "
            "FROM content_refs WHERE content_key=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      result.primary_logical_path = ColumnText(stmt, 0);
      result.primary_physical_path = ColumnText(stmt, 1);
      result.ref_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 2));
    }
    sqlite3_finalize(stmt);
    return result;
  }

  std::vector<FileMeta> ChildrenUnder(const std::string& logical_dir) {
    std::lock_guard<std::mutex> lock(mu_);
    std::string prefix = logical_dir;
    if (prefix != "/" && prefix.back() != '/') {
      prefix += "/";
    }
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
            "COALESCE(checksum,''),state "
            "FROM files WHERE logical_path LIKE ?;",
            &stmt);
    const std::string like = prefix + "%";
    sqlite3_bind_text(stmt, 1, like.c_str(), -1, SQLITE_TRANSIENT);
    std::vector<FileMeta> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      FileMeta meta;
      meta.logical_path = ColumnText(stmt, 0);
      meta.gpu_id = sqlite3_column_int(stmt, 1);
      meta.tier = ColumnText(stmt, 2);
      meta.backend_id = ColumnText(stmt, 3);
      meta.physical_path = ColumnText(stmt, 4);
      meta.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      meta.checksum = ColumnText(stmt, 6);
      meta.state = ColumnText(stmt, 7);
      out.push_back(std::move(meta));
    }
    sqlite3_finalize(stmt);
    return out;
  }

  std::vector<FileMeta> IncompleteFiles() {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
            "COALESCE(checksum,''),state "
            "FROM files WHERE state != 'COMMITTED';",
            &stmt);
    std::vector<FileMeta> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      FileMeta meta;
      meta.logical_path = ColumnText(stmt, 0);
      meta.gpu_id = sqlite3_column_int(stmt, 1);
      meta.tier = ColumnText(stmt, 2);
      meta.backend_id = ColumnText(stmt, 3);
      meta.physical_path = ColumnText(stmt, 4);
      meta.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      meta.checksum = ColumnText(stmt, 6);
      meta.state = ColumnText(stmt, 7);
      out.push_back(std::move(meta));
    }
    sqlite3_finalize(stmt);
    return out;
  }

  std::vector<EvictionCandidate> LocalEvictionCandidates(
      int gpu_id, const std::string& protected_logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
            "COALESCE(checksum,''),state,COALESCE(read_count,0),"
            "COALESCE(last_access_at,0),COALESCE(content_key,''),"
            "COALESCE(recompute_cost,10),COALESCE(remote_access_cost,10),"
            "COALESCE(producer_gpu,0),COALESCE(share_count,1),"
            "COALESCE(primary_tier,'local'),COALESCE(has_remote_copy,0),"
            "COALESCE(local_cache_owner_gpu,-1),"
            "COALESCE(replica_state,'LOCAL_ONLY'),COALESCE(cache_generation,0),"
            "COALESCE(last_promoted_at,0),COALESCE(last_demoted_at,0),"
            "COALESCE(dominant_gpu_id,-1),"
            "COALESCE(dominant_gpu_read_share_x100,0),"
            "COALESCE(recent_dominant_gpu_id,-1),"
            "COALESCE(recent_dominant_gpu_read_share_x100,0),"
            "COALESCE(recent_read_count,0),"
            "COALESCE(affinity_trend,'STABLE'),"
            "COALESCE(target_local_replica_count,0),"
            "COALESCE(affinity_state,'UNKNOWN'),COALESCE(affinity_updated_at,0) "
            "FROM files WHERE gpu_id=? AND tier='local' AND state='COMMITTED' "
            "AND logical_path != ? "
            "ORDER BY COALESCE(read_count,0) ASC,"
            "COALESCE(last_access_at,0) ASC,"
            "size_bytes DESC;",
            &stmt);
    sqlite3_bind_int(stmt, 1, gpu_id);
    sqlite3_bind_text(stmt, 2, protected_logical_path.c_str(), -1,
                      SQLITE_TRANSIENT);
    std::vector<EvictionCandidate> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      EvictionCandidate candidate;
      candidate.meta.logical_path = ColumnText(stmt, 0);
      candidate.meta.gpu_id = sqlite3_column_int(stmt, 1);
      candidate.meta.tier = ColumnText(stmt, 2);
      candidate.meta.backend_id = ColumnText(stmt, 3);
      candidate.meta.physical_path = ColumnText(stmt, 4);
      candidate.meta.size_bytes =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      candidate.meta.checksum = ColumnText(stmt, 6);
      candidate.meta.state = ColumnText(stmt, 7);
      candidate.meta.read_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 8));
      candidate.last_access_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 9));
      candidate.meta.content_key = ColumnText(stmt, 10);
      candidate.meta.recompute_cost =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 11));
      candidate.meta.remote_access_cost =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 12));
      candidate.meta.producer_gpu =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 13));
      candidate.meta.share_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 14));
      candidate.meta.primary_tier = ColumnText(stmt, 15);
      candidate.meta.has_remote_copy = sqlite3_column_int64(stmt, 16) != 0;
      candidate.meta.local_cache_owner_gpu = sqlite3_column_int(stmt, 17);
      candidate.meta.replica_state = ColumnText(stmt, 18);
      candidate.meta.cache_generation =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 19));
      candidate.meta.last_promoted_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 20));
      candidate.meta.last_demoted_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 21));
      candidate.meta.dominant_gpu_id = sqlite3_column_int(stmt, 22);
      candidate.meta.dominant_gpu_read_share_x100 =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 23));
      candidate.meta.recent_dominant_gpu_id = sqlite3_column_int(stmt, 24);
      candidate.meta.recent_dominant_gpu_read_share_x100 =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 25));
      candidate.meta.recent_read_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 26));
      candidate.meta.affinity_trend = ColumnText(stmt, 27);
      candidate.meta.target_local_replica_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 28));
      candidate.meta.affinity_state = ColumnText(stmt, 29);
      candidate.meta.affinity_updated_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 30));
      out.push_back(std::move(candidate));
    }
    sqlite3_finalize(stmt);
    return out;
  }

 private:
  void UpdateAffinityLocked(const std::string& logical_path,
                            uint64_t dominant_threshold_x100,
                            uint64_t shared_threshold_x100,
                            uint64_t short_window_sec,
                            uint64_t long_window_sec,
                            uint64_t trend_min_reads,
                            uint64_t hot_read_threshold,
                            uint64_t warm_read_threshold,
                            uint64_t max_local_replicas) {
    struct AccessStats {
      int dominant_gpu = -1;
      uint64_t dominant_reads = 0;
      uint64_t total_reads = 0;
      uint64_t gpu_count = 0;
      uint64_t dominant_share_x100 = 0;
    };

    auto finalize_stats = [](AccessStats stats) {
      if (stats.total_reads > 0) {
        stats.dominant_share_x100 =
            stats.dominant_reads * 100 / stats.total_reads;
      }
      return stats;
    };

    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT gpu_id,read_count FROM gpu_access WHERE logical_path=? "
            "ORDER BY read_count DESC,gpu_id ASC;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    AccessStats cumulative;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      const int current_gpu = sqlite3_column_int(stmt, 0);
      const uint64_t current_reads =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
      if (cumulative.gpu_count == 0) {
        cumulative.dominant_gpu = current_gpu;
        cumulative.dominant_reads = current_reads;
      }
      cumulative.total_reads += current_reads;
      ++cumulative.gpu_count;
    }
    sqlite3_finalize(stmt);
    cumulative = finalize_stats(cumulative);

    auto read_window_stats = [&](uint64_t window_sec) {
      AccessStats stats;
      const auto now = UnixNow();
      Prepare("SELECT gpu_id,COUNT(*) FROM gpu_access_events "
              "WHERE logical_path=? AND access_at>=? "
              "GROUP BY gpu_id ORDER BY COUNT(*) DESC,gpu_id ASC;",
              &stmt);
      sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_int64(stmt, 2,
                         now - static_cast<sqlite3_int64>(window_sec));
      while (true) {
        int rc = sqlite3_step(stmt);
        if (rc == SQLITE_DONE) {
          break;
        }
        if (rc != SQLITE_ROW) {
          std::string err = sqlite3_errmsg(db_);
          sqlite3_finalize(stmt);
          throw std::runtime_error(err);
        }
        const int current_gpu = sqlite3_column_int(stmt, 0);
        const uint64_t current_reads =
            static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
        if (stats.gpu_count == 0) {
          stats.dominant_gpu = current_gpu;
          stats.dominant_reads = current_reads;
        }
        stats.total_reads += current_reads;
        ++stats.gpu_count;
      }
      sqlite3_finalize(stmt);
      return finalize_stats(stats);
    };

    const AccessStats recent = read_window_stats(short_window_sec);
    const AccessStats longer = read_window_stats(long_window_sec);

    std::string state = "UNKNOWN";
    std::string trend = "STABLE";
    uint64_t target_local_replicas = 0;
    const uint64_t replica_cap = std::max<uint64_t>(1, max_local_replicas);

    if (recent.total_reads == 0) {
      state = "UNKNOWN";
    } else if (recent.total_reads < warm_read_threshold) {
      state = "REMOTE_COLD";
    } else if (recent.total_reads >= trend_min_reads &&
               recent.dominant_gpu >= 0 &&
               cumulative.dominant_gpu >= 0 &&
               recent.dominant_gpu != cumulative.dominant_gpu &&
               recent.dominant_share_x100 >= dominant_threshold_x100) {
      state = "AFFINITY_SHIFTING";
      trend = "SHIFTING_TO_GPU" + std::to_string(recent.dominant_gpu);
      target_local_replicas = 1;
    } else if (recent.gpu_count > 1 &&
               recent.dominant_share_x100 <= shared_threshold_x100) {
      if (recent.total_reads >= hot_read_threshold) {
        state = "REMOTE_SHARED_HOT";
        target_local_replicas = std::min<uint64_t>(recent.gpu_count, replica_cap);
      } else {
        state = "CROSS_GPU_SHARED";
      }
    } else if (recent.dominant_share_x100 >= dominant_threshold_x100) {
      if (recent.total_reads >= hot_read_threshold) {
        state = "GPU_LOCAL_HOT";
      } else {
        state = "GPU_LOCAL_WARM";
      }
      target_local_replicas = 1;
    } else {
      state = "MIXED_AFFINITY";
      target_local_replicas = 1;
    }

    if (trend == "STABLE" && longer.dominant_gpu >= 0 &&
        recent.dominant_gpu >= 0 && longer.dominant_gpu != recent.dominant_gpu) {
      trend = "OBSERVING_GPU" + std::to_string(recent.dominant_gpu);
    }

    Prepare("UPDATE files SET dominant_gpu_id=?,"
            "dominant_gpu_read_share_x100=?,recent_dominant_gpu_id=?,"
            "recent_dominant_gpu_read_share_x100=?,recent_read_count=?,"
            "affinity_trend=?,target_local_replica_count=?,"
            "affinity_state=?,affinity_updated_at=? WHERE logical_path=?;",
            &stmt);
    sqlite3_bind_int(stmt, 1, cumulative.dominant_gpu);
    sqlite3_bind_int64(
        stmt, 2, static_cast<sqlite3_int64>(cumulative.dominant_share_x100));
    sqlite3_bind_int(stmt, 3, recent.dominant_gpu);
    sqlite3_bind_int64(
        stmt, 4, static_cast<sqlite3_int64>(recent.dominant_share_x100));
    sqlite3_bind_int64(stmt, 5, static_cast<sqlite3_int64>(recent.total_reads));
    sqlite3_bind_text(stmt, 6, trend.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 7,
                       static_cast<sqlite3_int64>(target_local_replicas));
    sqlite3_bind_text(stmt, 8, state.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 9, UnixNow());
    sqlite3_bind_text(stmt, 10, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  static sqlite3_int64 UnixNow() {
    return static_cast<sqlite3_int64>(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
  }

  static std::string ColumnText(sqlite3_stmt* stmt, int col) {
    const auto* text = sqlite3_column_text(stmt, col);
    return text == nullptr ? "" : reinterpret_cast<const char*>(text);
  }

  void Exec(const char* sql) {
    char* err = nullptr;
    if (sqlite3_exec(db_, sql, nullptr, nullptr, &err) != SQLITE_OK) {
      std::string message = err == nullptr ? sqlite3_errmsg(db_) : err;
      sqlite3_free(err);
      throw std::runtime_error(message);
    }
  }

  void Prepare(const char* sql, sqlite3_stmt** stmt) {
    if (sqlite3_prepare_v2(db_, sql, -1, stmt, nullptr) != SQLITE_OK) {
      throw std::runtime_error(sqlite3_errmsg(db_));
    }
  }

  void EnsureColumn(const std::string& table, const std::string& column,
                    const std::string& definition) {
    sqlite3_stmt* stmt = nullptr;
    const std::string pragma = "PRAGMA table_info(" + table + ");";
    Prepare(pragma.c_str(), &stmt);
    bool found = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
      if (ColumnText(stmt, 1) == column) {
        found = true;
        break;
      }
    }
    sqlite3_finalize(stmt);
    if (!found) {
      const std::string sql =
          "ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition + ";";
      Exec(sql.c_str());
    }
  }

  void StepDone(sqlite3_stmt* stmt) {
    int rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
      std::string err = sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
      throw std::runtime_error(err);
    }
    sqlite3_finalize(stmt);
  }

  fs::path db_path_;
  sqlite3* db_ = nullptr;
  std::mutex mu_;
};

class TokenFS {
 public:
  explicit TokenFS(Config config)
      : config_(std::move(config)), metadata_(config_.metadata_db) {}

  void Init() {
    for (const auto& gpu : config_.gpus) {
      fs::create_directories(gpu.local_root);
      auto* backend = Backend(gpu.remote_backend);
      fs::create_directories(backend->root / GpuDirName(gpu.gpu_id));
    }
    fs::create_directories(config_.mount_point);
    metadata_.Open();
    RecoverIncompleteFiles();
  }

  int GetAttr(const char* cpath, struct stat* stbuf, fuse_file_info*) {
    memset(stbuf, 0, sizeof(*stbuf));
    const std::string path = Normalize(cpath);
    if (path == "/") {
      stbuf->st_mode = S_IFDIR | 0755;
      stbuf->st_nlink = 2;
      return 0;
    }
    if (const auto* gpu = GpuForRoot(path); gpu != nullptr) {
      stbuf->st_mode = S_IFDIR | 0755;
      stbuf->st_nlink = 2;
      return 0;
    }
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -ENOENT;
    }
    if (auto meta = metadata_.Get(path)) {
      return StatPhysical(meta->physical_path, stbuf);
    }
    const auto [gpu, rel] = *parsed;
    const auto local = gpu->local_root / rel;
    if (fs::exists(local)) {
      return StatPhysical(local, stbuf);
    }
    const auto remote = RemotePath(*gpu, rel);
    if (fs::exists(remote)) {
      return StatPhysical(remote, stbuf);
    }
    return -ENOENT;
  }

  int ReadDir(const char* cpath, void* buf, fuse_fill_dir_t filler, off_t,
              fuse_file_info*, enum fuse_readdir_flags) {
    const std::string path = Normalize(cpath);
    filler(buf, ".", nullptr, 0, static_cast<fuse_fill_dir_flags>(0));
    filler(buf, "..", nullptr, 0, static_cast<fuse_fill_dir_flags>(0));
    if (path == "/") {
      for (const auto& gpu : config_.gpus) {
        filler(buf, GpuDirName(gpu.gpu_id).c_str(), nullptr, 0,
               static_cast<fuse_fill_dir_flags>(0));
      }
      return 0;
    }

    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -ENOENT;
    }
    const auto [gpu, rel] = *parsed;
    std::set<std::string> names;
    AddDirectoryNames(gpu->local_root / rel, names);
    AddDirectoryNames(RemotePath(*gpu, rel), names);
    const std::string prefix = path == gpu->logical_root ? path : path + "/";
    for (const auto& meta : metadata_.ChildrenUnder(path)) {
      std::string rest = meta.logical_path.substr(prefix.size());
      auto slash = rest.find('/');
      names.insert(slash == std::string::npos ? rest : rest.substr(0, slash));
    }
    for (const auto& name : names) {
      filler(buf, name.c_str(), nullptr, 0, static_cast<fuse_fill_dir_flags>(0));
    }
    return 0;
  }

  int MkDir(const char* cpath, mode_t mode) {
    auto parsed = ParseGpuPath(Normalize(cpath));
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    std::error_code ec;
    fs::create_directories(gpu->local_root / rel, ec);
    if (ec) {
      return -ec.value();
    }
    fs::create_directories(RemotePath(*gpu, rel), ec);
    if (ec) {
      return -ec.value();
    }
    chmod((gpu->local_root / rel).c_str(), mode);
    chmod(RemotePath(*gpu, rel).c_str(), mode);
    return 0;
  }

  int RmDir(const char* cpath) {
    auto parsed = ParseGpuPath(Normalize(cpath));
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    std::error_code local_ec;
    std::error_code remote_ec;
    fs::remove(gpu->local_root / rel, local_ec);
    fs::remove(RemotePath(*gpu, rel), remote_ec);
    if (local_ec && remote_ec) {
      return -local_ec.value();
    }
    return 0;
  }

  int Create(const char* cpath, mode_t mode, fuse_file_info* fi) {
    const std::string path = Normalize(cpath);
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    FileMeta meta = SelectNewFile(*gpu, rel, path);
    fs::create_directories(meta.physical_path.parent_path());
    int fd = open(meta.physical_path.c_str(), fi->flags | O_CREAT, mode);
    if (fd < 0) {
      return -errno;
    }
    metadata_.Upsert(meta);
    Handle handle;
    handle.fd = fd;
    handle.logical_path = path;
    handle.gpu_id = gpu->gpu_id;
    handle.caller_gpu_id = DetectCallerGpuId(gpu->gpu_id);
    handle.tier = meta.tier;
    handle.backend_id = meta.backend_id;
    handle.physical_path = meta.physical_path;
    handle.flags = fi->flags;
    handle.writable = true;
    handle.created_remote = meta.tier == "remote";
    handle.state = "CREATING";
    fi->fh = StoreHandle(std::move(handle));
    return 0;
  }

  int Open(const char* cpath, fuse_file_info* fi) {
    const std::string path = Normalize(cpath);
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    FileMeta meta;
    if (auto existing = metadata_.Get(path)) {
      meta = *existing;
    } else {
      auto local = gpu->local_root / rel;
      if (fs::exists(local)) {
        meta.logical_path = path;
        meta.gpu_id = gpu->gpu_id;
        meta.tier = "local";
        meta.backend_id = "local";
        meta.physical_path = local;
        meta.size_bytes = FileSizeNoThrow(local);
        meta.state = "COMMITTED";
        meta.producer_gpu = static_cast<uint64_t>(gpu->gpu_id);
        meta.primary_tier = "local";
        meta.has_remote_copy = false;
        meta.local_cache_owner_gpu = gpu->gpu_id;
        meta.replica_state = "LOCAL_ONLY";
      } else {
        auto remote = RemotePath(*gpu, rel);
        if (!fs::exists(remote)) {
          return -ENOENT;
        }
        meta.logical_path = path;
        meta.gpu_id = gpu->gpu_id;
        meta.tier = "remote";
        meta.backend_id = gpu->remote_backend;
        meta.physical_path = remote;
        meta.size_bytes = FileSizeNoThrow(remote);
        meta.state = "COMMITTED";
        meta.producer_gpu = static_cast<uint64_t>(gpu->gpu_id);
        meta.primary_tier = "remote";
        meta.has_remote_copy = true;
        meta.local_cache_owner_gpu = -1;
        meta.replica_state = "REMOTE_ONLY";
      }
      metadata_.Upsert(meta);
    }
    const bool writable = IsWritable(fi->flags);
    const int caller_gpu_id = DetectCallerGpuId(gpu->gpu_id);
    if (!writable) {
      uint64_t read_count = metadata_.IncrementReadCount(
          path, caller_gpu_id, config_.affinity_dominant_threshold_x100,
          config_.affinity_shared_threshold_x100,
          config_.affinity_short_window_sec,
          config_.affinity_long_window_sec,
          config_.affinity_trend_min_reads,
          config_.affinity_hot_read_threshold,
          config_.affinity_warm_read_threshold,
          config_.max_local_replicas_per_file);
      meta.read_count = read_count;
      if (auto updated = metadata_.Get(path)) {
        meta = *updated;
      }
      MaybeManageCrossGpuReplica(meta, caller_gpu_id);
      if (auto updated = metadata_.Get(path)) {
        meta = *updated;
      }
      if (caller_gpu_id != gpu->gpu_id) {
        if (auto replica = metadata_.GetLocalReplica(path, caller_gpu_id);
            replica && replica->state == "READY" &&
            fs::exists(replica->physical_path)) {
          metadata_.TouchLocalReplica(path, caller_gpu_id);
          meta.tier = "local";
          meta.backend_id = "local-replica";
          meta.physical_path = replica->physical_path;
          meta.size_bytes = std::max(meta.size_bytes, replica->size_bytes);
          metadata_.AddMetric("cross_gpu_local_replica_hit", 1);
        }
      }
      metadata_.AddMetric("read_open_count", 1);
      metadata_.AddMetric(meta.tier == "local" ? "local_read_open_count"
                                                : "remote_read_open_count",
                          1);
      if (meta.tier == "remote" &&
          ShouldPromoteOnRead(meta, read_count, caller_gpu_id)) {
        if (int rc = PromoteToLocal(*gpu, rel, meta, "promote"); rc != 0) {
          metadata_.AddMetric("promote_error_count", 1);
        }
      }
      if (caller_gpu_id == gpu->gpu_id &&
          meta.affinity_state != "REMOTE_SHARED_HOT" &&
          meta.affinity_state != "CROSS_GPU_SHARED") {
        MaybeSchedulePrefetch(*gpu, rel);
      } else {
        metadata_.AddMetric("prefetch_skip_affinity", 1);
      }
    }
    int fd = open(meta.physical_path.c_str(), fi->flags);
    if (fd < 0) {
      return -errno;
    }
    if (writable) {
      meta.state = "CREATING";
      metadata_.Upsert(meta);
    }
    Handle handle;
    handle.fd = fd;
    handle.logical_path = path;
    handle.gpu_id = gpu->gpu_id;
    handle.caller_gpu_id = caller_gpu_id;
    handle.tier = meta.tier;
    handle.backend_id = meta.backend_id;
    handle.physical_path = meta.physical_path;
    handle.flags = fi->flags;
    handle.writable = writable;
    handle.state = meta.state;
    fi->fh = StoreHandle(std::move(handle));
    metadata_.AddMetric(meta.tier == "local" ? "open_local" : "open_remote", 1);
    return 0;
  }

  int Read(const char*, char* buf, size_t size, off_t offset,
           fuse_file_info* fi) {
    const auto start = Clock::now();
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    ApplyQos(*handle, false, size);
    ssize_t n = pread(handle->fd, buf, size, offset);
    if (n < 0) {
      return -errno;
    }
    metadata_.AddMetric("read_ops", 1);
    metadata_.AddMetric("read_bytes", static_cast<uint64_t>(n));
    metadata_.AddMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) + "_read_ops",
                        1);
    metadata_.AddMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) + "_read_bytes",
                        static_cast<uint64_t>(n));
    metadata_.AddMetric(handle->tier == "local" ? "read_local_ops" : "read_remote_ops",
                        1);
    metadata_.AddMetric(handle->tier == "local" ? "read_local_bytes"
                                                : "read_remote_bytes",
                        static_cast<uint64_t>(n));
    const uint64_t latency_us = ElapsedMicros(start);
    RecordLatency("read", handle->tier, latency_us);
    if (n > 0) {
      MaybeAdaptivePromote(*handle, latency_us);
    }
    return static_cast<int>(n);
  }

  int Write(const char*, const char* buf, size_t size, off_t offset,
            fuse_file_info* fi) {
    const auto start = Clock::now();
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    ApplyQos(*handle, true, size);
    if (int rc = SpillIfNeeded(*handle, static_cast<uint64_t>(offset + size));
        rc != 0) {
      return rc;
    }
    ssize_t n = pwrite(handle->fd, buf, size, offset);
    if (n < 0) {
      return -errno;
    }
    handle->state = "CREATING";
    UpdateHandleMeta(*handle, "CREATING");
    metadata_.AddMetric("write_ops", 1);
    metadata_.AddMetric("write_bytes", static_cast<uint64_t>(n));
    metadata_.AddMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) + "_write_ops",
                        1);
    metadata_.AddMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) + "_write_bytes",
                        static_cast<uint64_t>(n));
    metadata_.AddMetric(handle->tier == "local" ? "write_local_ops"
                                                : "write_remote_ops",
                        1);
    metadata_.AddMetric(handle->tier == "local" ? "write_local_bytes"
                                                : "write_remote_bytes",
                        static_cast<uint64_t>(n));
    const uint64_t latency_us = ElapsedMicros(start);
    RecordLatency("write", handle->tier, latency_us);
    return static_cast<int>(n);
  }

  int Release(const char*, fuse_file_info* fi) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    auto it = handles_.find(fi->fh);
    if (it == handles_.end()) {
      return 0;
    }
    bool should_dedup = false;
    if (it->second.fd >= 0) {
      if (it->second.writable) {
        int rc = CommitHandle(it->second);
        if (rc != 0) {
          close(it->second.fd);
          handles_.erase(it);
          return rc;
        }
      }
      close(it->second.fd);
      it->second.fd = -1;
      should_dedup = it->second.pending_physical_dedup;
    }
    if (should_dedup) {
      ApplyPhysicalDedup(it->second);
    }
    handles_.erase(it);
    return 0;
  }

  int Fsync(const char*, int datasync, fuse_file_info* fi) {
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    if (handle->writable) {
      metadata_.AddMetric("fsync_ops", 1);
      return CommitHandle(*handle);
    }
    int rc = datasync ? fdatasync(handle->fd) : fsync(handle->fd);
    if (rc != 0) {
      return -errno;
    }
    metadata_.AddMetric("fsync_ops", 1);
    return 0;
  }

  int Fallocate(const char*, int mode, off_t offset, off_t length,
                fuse_file_info* fi) {
    if ((mode & ~(FALLOC_FL_KEEP_SIZE)) != 0) {
      return -EOPNOTSUPP;
    }
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    const uint64_t end = static_cast<uint64_t>(offset + length);
    if ((mode & FALLOC_FL_KEEP_SIZE) == 0) {
      if (int rc = SpillIfNeeded(*handle, end); rc != 0) {
        return rc;
      }
    }
    int rc = posix_fallocate(handle->fd, offset, length);
    if (rc != 0) {
      return -rc;
    }
    handle->state = "CREATING";
    UpdateHandleMeta(*handle, "CREATING");
    metadata_.AddMetric("fallocate_ops", 1);
    metadata_.AddMetric("fallocate_bytes", static_cast<uint64_t>(length));
    return 0;
  }

  int Truncate(const char* cpath, off_t size, fuse_file_info* fi) {
    std::string path = Normalize(cpath);
    if (fi != nullptr && fi->fh != 0) {
      auto* handle = FindHandle(fi);
      if (handle == nullptr) {
        return -EBADF;
      }
      if (int rc = SpillIfNeeded(*handle, static_cast<uint64_t>(size)); rc != 0) {
        return rc;
      }
      if (ftruncate(handle->fd, size) != 0) {
        return -errno;
      }
      handle->state = "CREATING";
      UpdateHandleMeta(*handle, "CREATING");
      return CommitHandle(*handle);
    }
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    fuse_file_info tmp{};
    tmp.flags = O_RDWR;
    int rc = Open(cpath, &tmp);
    if (rc != 0) {
      return rc;
    }
    rc = Truncate(cpath, size, &tmp);
    Release(cpath, &tmp);
    return rc;
  }

  int Unlink(const char* cpath) {
    const std::string path = Normalize(cpath);
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    bool removed = false;
    if (auto meta = metadata_.Get(path)) {
      std::error_code ec;
      removed = fs::remove(meta->physical_path, ec) || removed;
    }
    for (const auto& replica : metadata_.LocalReplicas(path)) {
      std::error_code ec;
      removed = fs::remove(replica.physical_path, ec) || removed;
    }
    std::error_code local_ec;
    std::error_code remote_ec;
    removed = fs::remove(gpu->local_root / rel, local_ec) || removed;
    removed = fs::remove(RemotePath(*gpu, rel), remote_ec) || removed;
    metadata_.Remove(path);
    return removed ? 0 : -ENOENT;
  }

  int Rename(const char* cfrom, const char* cto, unsigned int flags) {
    if (flags != 0) {
      return -EINVAL;
    }
    const std::string from = Normalize(cfrom);
    const std::string to = Normalize(cto);
    auto from_parsed = ParseGpuPath(from);
    auto to_parsed = ParseGpuPath(to);
    if (!from_parsed || !to_parsed ||
        (*from_parsed).first->gpu_id != (*to_parsed).first->gpu_id) {
      return -EINVAL;
    }
    const auto [gpu, from_rel] = *from_parsed;
    const auto to_rel = (*to_parsed).second;
    if (auto meta = metadata_.Get(from)) {
      fs::path dest = meta->tier == "local" ? gpu->local_root / to_rel
                                            : RemotePath(*gpu, to_rel);
      fs::create_directories(dest.parent_path());
      std::error_code ec;
      fs::rename(meta->physical_path, dest, ec);
      if (ec) {
        return -ec.value();
      }
      if (meta->has_remote_copy && meta->tier == "local") {
        const fs::path old_remote = RemotePath(*gpu, from_rel);
        const fs::path new_remote = RemotePath(*gpu, to_rel);
        if (fs::exists(old_remote)) {
          fs::create_directories(new_remote.parent_path());
          std::error_code remote_ec;
          fs::rename(old_remote, new_remote, remote_ec);
          if (remote_ec) {
            return -remote_ec.value();
          }
        }
      }
      for (const auto& replica : metadata_.LocalReplicas(from)) {
        std::error_code replica_ec;
        fs::remove(replica.physical_path, replica_ec);
      }
      metadata_.RemoveLocalReplicas(from);
      meta->logical_path = to;
      meta->physical_path = dest;
      metadata_.Remove(from);
      metadata_.Upsert(*meta);
      return 0;
    }
    std::error_code local_ec;
    std::error_code remote_ec;
    fs::rename(gpu->local_root / from_rel, gpu->local_root / to_rel, local_ec);
    fs::rename(RemotePath(*gpu, from_rel), RemotePath(*gpu, to_rel), remote_ec);
    if (local_ec && remote_ec) {
      return -local_ec.value();
    }
    return 0;
  }

 private:
  static std::string Normalize(const char* cpath) {
    std::string path = cpath == nullptr ? "/" : cpath;
    if (path.empty()) {
      path = "/";
    }
    while (path.size() > 1 && path.back() == '/') {
      path.pop_back();
    }
    return path;
  }

  static std::string GpuDirName(int gpu_id) { return "gpu" + std::to_string(gpu_id); }

  const BackendConfig* Backend(const std::string& id) const {
    auto it = config_.backends.find(id);
    if (it == config_.backends.end()) {
      throw std::runtime_error("unknown backend: " + id);
    }
    return &it->second;
  }

  fs::path RemotePath(const GpuConfig& gpu, const fs::path& rel) const {
    return Backend(gpu.remote_backend)->root / GpuDirName(gpu.gpu_id) / rel;
  }

  const GpuConfig* GpuForRoot(const std::string& path) const {
    for (const auto& gpu : config_.gpus) {
      if (path == gpu.logical_root) {
        return &gpu;
      }
    }
    return nullptr;
  }

  const GpuConfig* GpuById(int gpu_id) const {
    for (const auto& gpu : config_.gpus) {
      if (gpu.gpu_id == gpu_id) {
        return &gpu;
      }
    }
    return nullptr;
  }

  std::optional<std::pair<const GpuConfig*, fs::path>> ParseGpuPath(
      const std::string& path) const {
    for (const auto& gpu : config_.gpus) {
      const std::string prefix = gpu.logical_root + "/";
      if (path.rfind(prefix, 0) == 0) {
        return std::make_pair(&gpu, fs::path(path.substr(prefix.size())));
      }
    }
    return std::nullopt;
  }

  fs::path CrossGpuReplicaPath(const GpuConfig& caller_gpu,
                               const GpuConfig& owner_gpu,
                               const fs::path& rel) const {
    return caller_gpu.local_root / ".tokenfs-replicas" /
           GpuDirName(owner_gpu.gpu_id) / rel;
  }

  bool KnownGpuId(int gpu_id) const {
    return std::any_of(config_.gpus.begin(), config_.gpus.end(),
                       [gpu_id](const GpuConfig& gpu) {
                         return gpu.gpu_id == gpu_id;
                       });
  }

  int DetectCallerGpuId(int fallback_gpu_id) {
    auto* ctx = fuse_get_context();
    if (ctx == nullptr || ctx->pid <= 0) {
      return fallback_gpu_id;
    }
    const fs::path environ_path =
        fs::path("/proc") / std::to_string(ctx->pid) / "environ";
    std::ifstream in(environ_path, std::ios::binary);
    if (!in) {
      metadata_.AddMetric("affinity_caller_env_unreadable", 1);
      return fallback_gpu_id;
    }
    std::string env((std::istreambuf_iterator<char>(in)),
                    std::istreambuf_iterator<char>());
    auto read_env_value = [&env](const std::string& key) -> std::optional<std::string> {
      size_t pos = 0;
      const std::string prefix = key + "=";
      while (pos < env.size()) {
        const size_t end = env.find('\0', pos);
        const size_t item_end = end == std::string::npos ? env.size() : end;
        std::string item = env.substr(pos, item_end - pos);
        if (item.rfind(prefix, 0) == 0) {
          return item.substr(prefix.size());
        }
        if (end == std::string::npos) {
          break;
        }
        pos = end + 1;
      }
      return std::nullopt;
    };

    auto parse_gpu = [](const std::string& value) -> std::optional<int> {
      std::string digits;
      for (char ch : value) {
        if (std::isdigit(static_cast<unsigned char>(ch))) {
          digits.push_back(ch);
        } else if (!digits.empty()) {
          break;
        }
      }
      if (digits.empty()) {
        return std::nullopt;
      }
      try {
        return std::stoi(digits);
      } catch (...) {
        return std::nullopt;
      }
    };

    for (const char* key : {"TOKENFS_GPU_ID", "CUDA_VISIBLE_DEVICES"}) {
      auto value = read_env_value(key);
      if (!value) {
        continue;
      }
      auto parsed = parse_gpu(*value);
      if (parsed && KnownGpuId(*parsed)) {
        if (*parsed != fallback_gpu_id) {
          metadata_.AddMetric("affinity_cross_gpu_caller_count", 1);
        }
        return *parsed;
      }
      metadata_.AddMetric("affinity_caller_env_invalid", 1);
    }
    return fallback_gpu_id;
  }

  static uint64_t FileSizeNoThrow(const fs::path& path) {
    std::error_code ec;
    auto size = fs::file_size(path, ec);
    return ec ? 0 : static_cast<uint64_t>(size);
  }

  static uint64_t UnixNowSeconds() {
    return static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
  }

  static uint64_t DataValueScore(const FileMeta& meta, uint64_t affinity_x100) {
    const uint64_t size_mib = std::max<uint64_t>(1, meta.size_bytes / 1024 / 1024);
    const uint64_t heat = meta.read_count;
    const uint64_t reuse_probability_x100 = std::min<uint64_t>(100, heat * 20);
    const uint64_t share_bonus = std::max<uint64_t>(1, meta.share_count);
    const uint64_t remote_cost_factor_x100 =
        std::max<uint64_t>(1, meta.remote_access_cost * 10);
    return
        (std::max<uint64_t>(1, reuse_probability_x100) *
         std::max<uint64_t>(1, meta.recompute_cost) *
         std::max<uint64_t>(1, affinity_x100) *
         remote_cost_factor_x100 *
         share_bonus) /
        (size_mib * 100);
  }

  static int64_t ValueAwareEvictionScore(const EvictionCandidate& candidate,
                                         uint64_t now) {
    const uint64_t size_mib =
        std::max<uint64_t>(1, candidate.meta.size_bytes / 1024 / 1024);
    const uint64_t age_minutes =
        candidate.last_access_at == 0 || now <= candidate.last_access_at
            ? 0
            : (now - candidate.last_access_at) / 60;
    const uint64_t affinity_x100 =
        candidate.meta.producer_gpu == static_cast<uint64_t>(candidate.meta.gpu_id)
            ? 100
            : 40;
    const uint64_t data_value = DataValueScore(candidate.meta, affinity_x100);

    return static_cast<int64_t>(size_mib * 1000 + age_minutes) -
           static_cast<int64_t>(data_value * 1000);
  }

  uint64_t CurrentAffinityX100(const FileMeta& meta, int gpu_id) {
    uint64_t affinity = metadata_.AccessAffinityX100(meta.logical_path, gpu_id);
    if (affinity == 0 && meta.producer_gpu == static_cast<uint64_t>(gpu_id)) {
      affinity = 100;
    }
    return affinity == 0 ? 40 : affinity;
  }

  static bool IsWritable(int flags) {
    const int mode = flags & O_ACCMODE;
    return mode == O_WRONLY || mode == O_RDWR || (flags & O_TRUNC) != 0;
  }

  static uint64_t DirectoryBytes(const fs::path& root) {
    uint64_t total = 0;
    std::error_code ec;
    if (!fs::exists(root, ec)) {
      return 0;
    }
    for (fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec), end;
         it != end && !ec; it.increment(ec)) {
      if (it->is_regular_file(ec)) {
        total += static_cast<uint64_t>(it->file_size(ec));
      }
    }
    return total;
  }

  static std::optional<fs::path> NextSequentialRelPath(const fs::path& rel) {
    const std::string filename = rel.filename().string();
    const size_t dot = filename.rfind('.');
    const size_t number_end = dot == std::string::npos ? filename.size() : dot;
    size_t number_begin = number_end;
    while (number_begin > 0 &&
           std::isdigit(static_cast<unsigned char>(filename[number_begin - 1]))) {
      --number_begin;
    }
    if (number_begin == number_end) {
      return std::nullopt;
    }

    const std::string digits = filename.substr(number_begin, number_end - number_begin);
    uint64_t value = 0;
    try {
      value = std::stoull(digits);
    } catch (...) {
      return std::nullopt;
    }
    std::ostringstream next_digits;
    next_digits << std::setw(static_cast<int>(digits.size())) << std::setfill('0')
                << (value + 1);
    fs::path next =
        filename.substr(0, number_begin) + next_digits.str() + filename.substr(number_end);
    if (!rel.parent_path().empty()) {
      next = rel.parent_path() / next;
    }
    return next;
  }

  bool HasLocalCapacity(const GpuConfig& gpu, uint64_t new_file_size,
                        const fs::path* existing_file = nullptr) const {
    uint64_t used = DirectoryBytes(gpu.local_root);
    if (existing_file != nullptr) {
      uint64_t existing_size = FileSizeNoThrow(*existing_file);
      if (used >= existing_size) {
        used -= existing_size;
      }
    }
    return used + new_file_size <= gpu.local_quota_bytes;
  }

  bool EnsureLocalCapacity(const GpuConfig& gpu, uint64_t required_size,
                           const std::string& protected_logical_path,
                           const fs::path* existing_file = nullptr) {
    if (required_size > gpu.local_quota_bytes) {
      return false;
    }
    uint64_t used = DirectoryBytes(gpu.local_root);
    if (existing_file != nullptr) {
      uint64_t existing_size = FileSizeNoThrow(*existing_file);
      if (used >= existing_size) {
        used -= existing_size;
      }
    }
    if (used + required_size <= gpu.local_quota_bytes) {
      return true;
    }
    const std::string policy = config_.local_eviction_policy;
    if (policy != "cost_aware" && policy != "value_aware" &&
        policy != "lru" && policy != "lfu") {
      return false;
    }

    auto candidates =
        metadata_.LocalEvictionCandidates(gpu.gpu_id, protected_logical_path);
    const uint64_t now = UnixNowSeconds();
    if (policy == "lru") {
      metadata_.AddMetric("evict_policy_lru", 1);
      std::sort(candidates.begin(), candidates.end(),
                [](const EvictionCandidate& lhs,
                   const EvictionCandidate& rhs) {
                  if (lhs.last_access_at != rhs.last_access_at) {
                    return lhs.last_access_at < rhs.last_access_at;
                  }
                  if (lhs.meta.read_count != rhs.meta.read_count) {
                    return lhs.meta.read_count < rhs.meta.read_count;
                  }
                  return lhs.meta.size_bytes > rhs.meta.size_bytes;
                });
    } else if (policy == "lfu") {
      metadata_.AddMetric("evict_policy_lfu", 1);
      std::sort(candidates.begin(), candidates.end(),
                [](const EvictionCandidate& lhs,
                   const EvictionCandidate& rhs) {
                  if (lhs.meta.read_count != rhs.meta.read_count) {
                    return lhs.meta.read_count < rhs.meta.read_count;
                  }
                  if (lhs.last_access_at != rhs.last_access_at) {
                    return lhs.last_access_at < rhs.last_access_at;
                  }
                  return lhs.meta.size_bytes > rhs.meta.size_bytes;
                });
    } else {
      metadata_.AddMetric("evict_policy_value_aware", 1);
      std::sort(candidates.begin(), candidates.end(),
                [now](const EvictionCandidate& lhs,
                      const EvictionCandidate& rhs) {
                  const auto lhs_score = ValueAwareEvictionScore(lhs, now);
                  const auto rhs_score = ValueAwareEvictionScore(rhs, now);
                  if (lhs_score != rhs_score) {
                    return lhs_score > rhs_score;
                  }
                  return lhs.meta.size_bytes > rhs.meta.size_bytes;
                });
    }

    for (auto candidate : candidates) {
      if (IsOpenLogicalPath(candidate.meta.logical_path)) {
        metadata_.AddMetric("evict_skip_open", 1);
        continue;
      }
      if ((policy == "cost_aware" || policy == "value_aware") &&
          ValueAwareEvictionScore(candidate, now) < 0) {
        metadata_.AddMetric("evict_skip_hot", 1);
        continue;
      }
      const uint64_t candidate_size =
          std::max(candidate.meta.size_bytes, FileSizeNoThrow(candidate.meta.physical_path));
      if (candidate_size == 0 || !fs::exists(candidate.meta.physical_path)) {
        continue;
      }
      if (int rc = EvictLocalFile(gpu, candidate.meta); rc != 0) {
        metadata_.AddMetric("evict_error_count", 1);
        continue;
      }
      used = used > candidate_size ? used - candidate_size : 0;
      if (used + required_size <= gpu.local_quota_bytes) {
        return true;
      }
    }
    return used + required_size <= gpu.local_quota_bytes;
  }

  FileMeta SelectNewFile(const GpuConfig& gpu, const fs::path& rel,
                         const std::string& logical_path) const {
    const uint64_t used = DirectoryBytes(gpu.local_root);
    FileMeta meta;
    meta.logical_path = logical_path;
    meta.gpu_id = gpu.gpu_id;
    meta.recompute_cost = config_.default_recompute_cost;
    meta.remote_access_cost = config_.default_remote_access_cost;
    meta.producer_gpu = static_cast<uint64_t>(gpu.gpu_id);
    meta.share_count = 1;
    meta.state = "CREATING";
    if (used < gpu.local_quota_bytes) {
      meta.tier = "local";
      meta.backend_id = "local";
      meta.physical_path = gpu.local_root / rel;
      meta.primary_tier = "local";
      meta.has_remote_copy = false;
      meta.local_cache_owner_gpu = gpu.gpu_id;
      meta.replica_state = "LOCAL_ONLY";
      return meta;
    }
    meta.tier = "remote";
    meta.backend_id = gpu.remote_backend;
    meta.physical_path = RemotePath(gpu, rel);
    meta.primary_tier = "remote";
    meta.has_remote_copy = true;
    meta.local_cache_owner_gpu = -1;
    meta.replica_state = "REMOTE_ONLY";
    return meta;
  }

  bool ShouldPromoteOnRead(FileMeta meta, uint64_t read_count, int gpu_id) {
    if (meta.state != "COMMITTED" || meta.tier != "remote") {
      return false;
    }
    meta.read_count = read_count;
    if (gpu_id != meta.gpu_id) {
      metadata_.AddMetric("affinity_cross_gpu_promote_skip", 1);
      return false;
    }
    if (meta.affinity_state == "REMOTE_SHARED_HOT" ||
        meta.affinity_state == "CROSS_GPU_SHARED") {
      metadata_.AddMetric("affinity_shared_remote_preferred_skip", 1);
      return false;
    }
    if (meta.affinity_state == "REMOTE_COLD") {
      metadata_.AddMetric("affinity_remote_cold_promote_skip", 1);
      return false;
    }
    if (meta.dominant_gpu_id >= 0 && meta.dominant_gpu_id != gpu_id &&
        meta.dominant_gpu_read_share_x100 >=
            config_.affinity_dominant_threshold_x100) {
      metadata_.AddMetric("affinity_non_dominant_promote_skip", 1);
      return false;
    }
    if (config_.promote_on_read && read_count >= config_.promote_read_threshold) {
      return true;
    }
    if (config_.placement_policy == "value_aware" && config_.adaptive_migration) {
      const uint64_t value =
          DataValueScore(meta, CurrentAffinityX100(meta, gpu_id));
      return value >= config_.value_promote_threshold;
    }
    return false;
  }

  bool ShouldCreateCrossGpuReplica(const FileMeta& meta, int caller_gpu_id) {
    if (!config_.cross_gpu_local_cache || caller_gpu_id == meta.gpu_id ||
        meta.state != "COMMITTED" || !meta.has_remote_copy) {
      return false;
    }
    if (meta.target_local_replica_count == 0) {
      metadata_.AddMetric("cross_gpu_replica_skip_target_zero", 1);
      return false;
    }
    if (meta.affinity_state != "REMOTE_SHARED_HOT" &&
        meta.affinity_state != "AFFINITY_SHIFTING" &&
        meta.affinity_state != "GPU_LOCAL_HOT" &&
        meta.affinity_state != "GPU_LOCAL_WARM") {
      metadata_.AddMetric("cross_gpu_replica_skip_state", 1);
      return false;
    }
    if (meta.affinity_state == "AFFINITY_SHIFTING" &&
        meta.recent_dominant_gpu_id != caller_gpu_id) {
      metadata_.AddMetric("cross_gpu_replica_skip_non_recent_dominant", 1);
      return false;
    }
    if ((meta.affinity_state == "GPU_LOCAL_HOT" ||
         meta.affinity_state == "GPU_LOCAL_WARM") &&
        meta.recent_dominant_gpu_id != caller_gpu_id) {
      metadata_.AddMetric("cross_gpu_replica_skip_non_recent_dominant", 1);
      return false;
    }
    const uint64_t now = UnixNowSeconds();
    if (meta.last_promoted_at > 0 &&
        now < meta.last_promoted_at + config_.affinity_replica_cooldown_sec) {
      metadata_.AddMetric("cross_gpu_replica_skip_cooldown", 1);
      return false;
    }
    return true;
  }

  void MaybeManageCrossGpuReplica(const FileMeta& meta, int caller_gpu_id) {
    ReconcileCrossGpuReplicas(meta);
    auto parsed = ParseGpuPath(meta.logical_path);
    if (!parsed) {
      return;
    }
    const auto [owner_gpu, rel] = *parsed;
    const auto* caller_gpu = GpuById(caller_gpu_id);
    if (caller_gpu == nullptr || caller_gpu->gpu_id == owner_gpu->gpu_id) {
      return;
    }
    if (auto existing =
            metadata_.GetLocalReplica(meta.logical_path, caller_gpu_id)) {
      if (existing->state == "READY" && fs::exists(existing->physical_path)) {
        metadata_.TouchLocalReplica(meta.logical_path, caller_gpu_id);
        metadata_.AddMetric("cross_gpu_replica_reuse_count", 1);
        return;
      }
      metadata_.RemoveLocalReplica(meta.logical_path, caller_gpu_id);
    }
    if (!ShouldCreateCrossGpuReplica(meta, caller_gpu_id)) {
      return;
    }
    if (metadata_.LocalReplicas(meta.logical_path).size() >=
        meta.target_local_replica_count) {
      ReconcileCrossGpuReplicas(meta);
      if (metadata_.LocalReplicas(meta.logical_path).size() >=
          meta.target_local_replica_count) {
        metadata_.AddMetric("cross_gpu_replica_skip_cap", 1);
        return;
      }
    }
    CreateCrossGpuReplica(*caller_gpu, *owner_gpu, rel, meta);
  }

  void CreateCrossGpuReplica(const GpuConfig& caller_gpu,
                             const GpuConfig& owner_gpu, const fs::path& rel,
                             FileMeta meta) {
    fs::path source = RemotePath(owner_gpu, rel);
    if (!fs::exists(source)) {
      source = meta.physical_path;
    }
    if (!fs::exists(source)) {
      metadata_.AddMetric("cross_gpu_replica_skip_missing_source", 1);
      return;
    }
    const uint64_t size = FileSizeNoThrow(source);
    fs::path local = CrossGpuReplicaPath(caller_gpu, owner_gpu, rel);
    if (!EnsureLocalCapacity(caller_gpu, size, meta.logical_path,
                             fs::exists(local) ? &local : nullptr)) {
      metadata_.AddMetric("cross_gpu_replica_skip_no_space", 1);
      return;
    }
    ApplyBackgroundQos(caller_gpu.gpu_id, size, "cross_gpu_replica");
    fs::create_directories(local.parent_path());
    fs::path tmp = local;
    tmp += config_.temp_suffix + ".xgpu";
    std::error_code ec;
    fs::remove(tmp, ec);
    ec.clear();
    fs::copy_file(source, tmp, fs::copy_options::overwrite_existing, ec);
    if (ec) {
      fs::remove(tmp, ec);
      metadata_.AddMetric("cross_gpu_replica_error_count", 1);
      return;
    }
    int fd = open(tmp.c_str(), O_RDONLY);
    if (fd >= 0) {
      fsync(fd);
      close(fd);
    }
    fs::rename(tmp, local, ec);
    if (ec) {
      fs::remove(tmp, ec);
      metadata_.AddMetric("cross_gpu_replica_error_count", 1);
      return;
    }
    const uint64_t now = UnixNowSeconds();
    LocalReplica replica;
    replica.logical_path = meta.logical_path;
    replica.gpu_id = caller_gpu.gpu_id;
    replica.physical_path = local;
    replica.size_bytes = size;
    replica.cache_generation = meta.cache_generation + 1;
    replica.created_at = now;
    replica.last_access_at = now;
    replica.state = "READY";
    metadata_.UpsertLocalReplica(replica);
    meta.last_promoted_at = now;
    meta.target_local_replica_count =
        std::max<uint64_t>(meta.target_local_replica_count, 1);
    metadata_.Upsert(meta);
    metadata_.AddMetric("cross_gpu_replica_create_count", 1);
    metadata_.AddMetric("cross_gpu_replica_create_bytes", size);
  }

  void ReconcileCrossGpuReplicas(const FileMeta& meta) {
    auto replicas = metadata_.LocalReplicas(meta.logical_path);
    if (replicas.empty()) {
      return;
    }
    const uint64_t now = UnixNowSeconds();
    const uint64_t target = meta.target_local_replica_count;
    if (replicas.size() <= target) {
      return;
    }
    std::sort(replicas.begin(), replicas.end(),
              [](const LocalReplica& lhs, const LocalReplica& rhs) {
                if (lhs.last_access_at != rhs.last_access_at) {
                  return lhs.last_access_at < rhs.last_access_at;
                }
                return lhs.created_at < rhs.created_at;
              });
    while (replicas.size() > target) {
      const auto replica = replicas.front();
      if (now < replica.created_at + config_.affinity_replica_min_residency_sec) {
        metadata_.AddMetric("cross_gpu_replica_keep_min_residency", 1);
        break;
      }
      std::error_code ec;
      fs::remove(replica.physical_path, ec);
      metadata_.RemoveLocalReplica(replica.logical_path, replica.gpu_id);
      metadata_.AddMetric("cross_gpu_replica_delete_count", 1);
      metadata_.AddMetric("cross_gpu_replica_delete_bytes", replica.size_bytes);
      replicas.erase(replicas.begin());
    }
  }

  int PromoteToLocal(const GpuConfig& gpu, const fs::path& rel, FileMeta& meta,
                     const std::string& metric_prefix) {
    const uint64_t size = FileSizeNoThrow(meta.physical_path);
    ApplyBackgroundQos(gpu.gpu_id, size, metric_prefix);
    fs::path local = gpu.local_root / rel;
    const fs::path source = meta.physical_path;
    if (!EnsureLocalCapacity(gpu, size, meta.logical_path,
                             fs::exists(local) ? &local : nullptr)) {
      metadata_.AddMetric(metric_prefix + "_skip_no_space", 1);
      return 0;
    }

    fs::create_directories(local.parent_path());
    fs::path tmp = local;
    tmp += config_.temp_suffix + ".promote";

    std::error_code ec;
    fs::remove(tmp, ec);
    ec.clear();

    FileMeta migrating = meta;
    migrating.state = "COPYING_TO_LOCAL";
    metadata_.Upsert(migrating);
    metadata_.AddMetric("migration_to_local_begin", 1);

    fs::copy_file(source, tmp, fs::copy_options::overwrite_existing, ec);
    if (ec) {
      fs::remove(tmp, ec);
      return -ec.value();
    }

    int fd = open(tmp.c_str(), O_RDONLY);
    if (fd < 0) {
      fs::remove(tmp, ec);
      return -errno;
    }
    if (fsync(fd) != 0) {
      int err = errno;
      close(fd);
      fs::remove(tmp, ec);
      return -err;
    }
    close(fd);

    fs::rename(tmp, local, ec);
    if (ec) {
      fs::remove(tmp, ec);
      return -ec.value();
    }

    meta.tier = "local";
    meta.backend_id = "local";
    meta.physical_path = local;
    meta.size_bytes = size;
    meta.primary_tier = "remote";
    meta.has_remote_copy = true;
    meta.local_cache_owner_gpu = gpu.gpu_id;
    meta.replica_state = "REMOTE_WITH_LOCAL_CACHE";
    meta.cache_generation += 1;
    meta.last_promoted_at = UnixNowSeconds();
    meta.state = "LOCAL_READY";
    metadata_.Upsert(meta);
    meta.state = "COMMITTED";
    metadata_.Upsert(meta);
    metadata_.AddMetric("migration_to_local_commit", 1);
    metadata_.AddMetric("local_cache_create_count", 1);
    metadata_.AddMetric(metric_prefix + "_count", 1);
    metadata_.AddMetric(metric_prefix + "_bytes", size);
    return 0;
  }

  void MaybeSchedulePrefetch(const GpuConfig& gpu, const fs::path& rel) {
    if (!config_.prefetch_on_read) {
      return;
    }
    auto next_rel = NextSequentialRelPath(rel);
    if (!next_rel) {
      return;
    }
    const std::string next_logical =
        gpu.logical_root + "/" + next_rel->generic_string();
    const fs::path local = gpu.local_root / *next_rel;
    if (fs::exists(local)) {
      metadata_.AddMetric("prefetch_skip_local", 1);
      return;
    }
    const fs::path remote = RemotePath(gpu, *next_rel);
    if (!fs::exists(remote)) {
      if (auto meta = metadata_.Get(next_logical); !meta || meta->tier != "remote") {
        metadata_.AddMetric("prefetch_skip_missing", 1);
        return;
      }
    }

    {
      std::lock_guard<std::mutex> lock(prefetch_mu_);
      if (prefetch_inflight_.count(next_logical) != 0) {
        return;
      }
      prefetch_inflight_.insert(next_logical);
    }

    metadata_.AddMetric("prefetch_request_count", 1);
    std::thread([this, gpu, next_rel = *next_rel, next_logical]() {
      PrefetchToLocal(gpu, next_rel, next_logical);
      std::lock_guard<std::mutex> lock(prefetch_mu_);
      prefetch_inflight_.erase(next_logical);
    }).detach();
  }

  void PrefetchToLocal(const GpuConfig& gpu, const fs::path& rel,
                       const std::string& logical_path) {
    FileMeta meta;
    if (auto existing = metadata_.Get(logical_path)) {
      meta = *existing;
      if (meta.tier == "local") {
        metadata_.AddMetric("prefetch_skip_local", 1);
        return;
      }
    } else {
      fs::path remote = RemotePath(gpu, rel);
      if (!fs::exists(remote)) {
        metadata_.AddMetric("prefetch_skip_missing", 1);
        return;
      }
      meta.logical_path = logical_path;
      meta.gpu_id = gpu.gpu_id;
      meta.tier = "remote";
      meta.backend_id = gpu.remote_backend;
      meta.physical_path = remote;
      meta.size_bytes = FileSizeNoThrow(remote);
      meta.state = "COMMITTED";
      meta.recompute_cost = config_.default_recompute_cost;
      meta.remote_access_cost = config_.default_remote_access_cost;
      meta.producer_gpu = static_cast<uint64_t>(gpu.gpu_id);
      meta.share_count = 1;
      metadata_.Upsert(meta);
    }

    if (meta.state != "COMMITTED" || !fs::exists(meta.physical_path)) {
      metadata_.AddMetric("prefetch_skip_missing", 1);
      return;
    }
    if (int rc = PromoteToLocal(gpu, rel, meta, "prefetch"); rc != 0) {
      metadata_.AddMetric("prefetch_error_count", 1);
    }
  }

  int SpillIfNeeded(Handle& handle, uint64_t new_size) {
    if (handle.tier != "local") {
      return 0;
    }
    const GpuConfig* gpu = nullptr;
    for (const auto& item : config_.gpus) {
      if (item.gpu_id == handle.gpu_id) {
        gpu = &item;
        break;
      }
    }
    if (gpu == nullptr) {
      return -EINVAL;
    }
    uint64_t current = FileSizeNoThrow(handle.physical_path);
    uint64_t used_without_file = DirectoryBytes(gpu->local_root);
    if (used_without_file >= current) {
      used_without_file -= current;
    }
    if (used_without_file + new_size <= gpu->local_quota_bytes) {
      return 0;
    }
    if (EnsureLocalCapacity(*gpu, new_size, handle.logical_path,
                            &handle.physical_path)) {
      return 0;
    }

    auto parsed = ParseGpuPath(handle.logical_path);
    if (!parsed) {
      return -EINVAL;
    }
    fs::path remote = RemotePath(*gpu, parsed->second);
    const uint64_t moved_bytes = FileSizeNoThrow(handle.physical_path);
    fs::create_directories(remote.parent_path());
    if (handle.fd >= 0) {
      fsync(handle.fd);
      close(handle.fd);
      handle.fd = -1;
    }
    std::error_code ec;
    fs::rename(handle.physical_path, remote, ec);
    if (ec) {
      fs::copy_file(handle.physical_path, remote,
                    fs::copy_options::overwrite_existing, ec);
      if (ec) {
        return -ec.value();
      }
      fs::remove(handle.physical_path, ec);
    }
    handle.physical_path = remote;
    handle.tier = "remote";
    handle.backend_id = gpu->remote_backend;
    handle.created_remote = false;
    handle.fd = open(handle.physical_path.c_str(), handle.flags);
    if (handle.fd < 0) {
      return -errno;
    }
    UpdateHandleMeta(handle, handle.state);
    if (auto meta = metadata_.Get(handle.logical_path)) {
      meta->primary_tier = "remote";
      meta->has_remote_copy = true;
      meta->local_cache_owner_gpu = -1;
      meta->replica_state = "REMOTE_ONLY";
      meta->last_demoted_at = UnixNowSeconds();
      metadata_.Upsert(*meta);
    }
    metadata_.AddMetric("spill_count", 1);
    metadata_.AddMetric("spill_bytes", std::max(moved_bytes, new_size));
    return 0;
  }

  int EvictLocalFile(const GpuConfig& gpu, FileMeta& meta) {
    auto parsed = ParseGpuPath(meta.logical_path);
    if (!parsed) {
      return -EINVAL;
    }
    fs::path remote = RemotePath(gpu, parsed->second);
    const uint64_t size = FileSizeNoThrow(meta.physical_path);
    const fs::path source = meta.physical_path;
    ApplyBackgroundQos(gpu.gpu_id, size, "evict");

    std::error_code ec;
    if (meta.has_remote_copy && fs::exists(remote, ec)) {
      FileMeta deleting = meta;
      deleting.state = "DELETING_CACHE";
      metadata_.Upsert(deleting);

      fs::remove(source, ec);
      if (ec) {
        return -ec.value();
      }

      meta.tier = "remote";
      meta.backend_id = gpu.remote_backend;
      meta.physical_path = remote;
      meta.size_bytes = std::max(size, FileSizeNoThrow(remote));
      meta.primary_tier = "remote";
      meta.has_remote_copy = true;
      meta.local_cache_owner_gpu = -1;
      meta.replica_state = "REMOTE_ONLY";
      meta.last_demoted_at = UnixNowSeconds();
      meta.state = "COMMITTED";
      metadata_.Upsert(meta);
      metadata_.AddMetric("local_cache_delete_count", 1);
      metadata_.AddMetric("local_cache_delete_bytes", size);
      metadata_.AddMetric("evict_count", 1);
      metadata_.AddMetric("evict_bytes", size);
      return 0;
    }

    fs::create_directories(remote.parent_path());
    fs::path tmp = remote;
    tmp += config_.temp_suffix + ".evict";

    fs::remove(tmp, ec);
    ec.clear();

    FileMeta migrating = meta;
    migrating.state = "COPYING_TO_REMOTE";
    metadata_.Upsert(migrating);
    metadata_.AddMetric("migration_to_remote_begin", 1);

    fs::copy_file(source, tmp, fs::copy_options::overwrite_existing, ec);
    if (ec) {
      fs::remove(tmp, ec);
      return -ec.value();
    }
    if (int fd = open(tmp.c_str(), O_RDONLY); fd >= 0) {
      fsync(fd);
      close(fd);
    }
    fs::rename(tmp, remote, ec);
    if (ec) {
      fs::remove(tmp, ec);
      return -ec.value();
    }

    meta.tier = "remote";
    meta.backend_id = gpu.remote_backend;
    meta.physical_path = remote;
    meta.size_bytes = size;
    meta.primary_tier = "remote";
    meta.has_remote_copy = true;
    meta.local_cache_owner_gpu = -1;
    meta.replica_state = "REMOTE_ONLY";
    meta.last_demoted_at = UnixNowSeconds();
    meta.state = "REMOTE_READY";
    metadata_.Upsert(meta);
    meta.state = "COMMITTED";
    metadata_.Upsert(meta);
    fs::remove(source, ec);
    metadata_.AddMetric("migration_to_remote_commit", 1);
    metadata_.AddMetric("evict_count", 1);
    metadata_.AddMetric("evict_bytes", size);
    return 0;
  }

  void UpdateHandleMeta(const Handle& handle, const std::string& state,
                        const std::string& checksum = "") {
    FileMeta meta;
    if (auto existing = metadata_.Get(handle.logical_path)) {
      meta = *existing;
    }
    meta.logical_path = handle.logical_path;
    meta.gpu_id = handle.gpu_id;
    meta.tier = handle.tier;
    meta.backend_id = handle.backend_id;
    meta.physical_path = handle.physical_path;
    meta.size_bytes = FileSizeNoThrow(handle.physical_path);
    meta.checksum = checksum;
    if (config_.physical_dedup && !checksum.empty()) {
      meta.content_key = checksum;
    }
    if (meta.recompute_cost == 0) {
      meta.recompute_cost = config_.default_recompute_cost;
    }
    if (meta.remote_access_cost == 0) {
      meta.remote_access_cost = config_.default_remote_access_cost;
    }
    if (meta.producer_gpu == 0 && handle.gpu_id != 0) {
      meta.producer_gpu = static_cast<uint64_t>(handle.gpu_id);
    }
    if (meta.share_count == 0) {
      meta.share_count = 1;
    }
    if (handle.tier == "remote") {
      meta.primary_tier = "remote";
      meta.has_remote_copy = true;
      meta.local_cache_owner_gpu = -1;
      meta.replica_state = "REMOTE_ONLY";
    } else if (meta.primary_tier.empty()) {
      meta.primary_tier = "local";
      meta.has_remote_copy = false;
      meta.local_cache_owner_gpu = handle.gpu_id;
      meta.replica_state = "LOCAL_ONLY";
    } else if (meta.primary_tier == "local" && !meta.has_remote_copy) {
      meta.local_cache_owner_gpu = handle.gpu_id;
      meta.replica_state = "LOCAL_ONLY";
    }
    meta.state = state;
    metadata_.Upsert(meta);
  }

  int CommitHandle(Handle& handle) {
    if (handle.fd < 0) {
      return -EBADF;
    }
    if (fsync(handle.fd) != 0) {
      return -errno;
    }
    std::string checksum;
    if (config_.checksum != "none") {
      auto calculated = ChecksumFile(handle.physical_path);
      if (!calculated) {
        return -EIO;
      }
      checksum = *calculated;
    }
    handle.state = "COMMITTED";
    UpdateHandleMeta(handle, "COMMITTED", checksum);
    handle.last_checksum = checksum;
    if (config_.physical_dedup && !checksum.empty()) {
      auto content_ref = metadata_.RegisterContentRef(
          checksum, handle.logical_path, handle.physical_path,
          FileSizeNoThrow(handle.physical_path));
      if (content_ref.duplicate) {
        metadata_.AddMetric("dedup_duplicate_content_count", 1);
      }
      metadata_.AddMetric("content_ref_register_count", 1);
      if (config_.physical_dedup && content_ref.duplicate &&
          !content_ref.primary_physical_path.empty() &&
          content_ref.primary_physical_path != handle.physical_path) {
        handle.pending_physical_dedup = true;
        handle.dedup_primary_path = content_ref.primary_physical_path;
        metadata_.AddMetric("physical_dedup_candidate_count", 1);
      }
    }
    if (handle.created_remote) {
      metadata_.AddMetric("remote_place_count", 1);
      handle.created_remote = false;
    }
    return 0;
  }

  int ApplyPhysicalDedup(const Handle& handle) {
    if (!config_.physical_dedup || !handle.pending_physical_dedup ||
        handle.dedup_primary_path.empty()) {
      return 0;
    }
    std::error_code ec;
    if (!fs::exists(handle.dedup_primary_path, ec) ||
        !fs::exists(handle.physical_path, ec)) {
      metadata_.AddMetric("physical_dedup_skip_missing", 1);
      return 0;
    }
    ec.clear();
    if (fs::equivalent(handle.dedup_primary_path, handle.physical_path, ec)) {
      return 0;
    }

    fs::path tmp = handle.physical_path;
    tmp += config_.temp_suffix + ".dedup";
    fs::remove(tmp, ec);
    ec.clear();
    fs::create_hard_link(handle.dedup_primary_path, tmp, ec);
    if (ec) {
      metadata_.AddMetric("physical_dedup_hardlink_fail", 1);
      return 0;
    }
    ec.clear();
    fs::rename(tmp, handle.physical_path, ec);
    if (ec) {
      fs::remove(tmp, ec);
      metadata_.AddMetric("physical_dedup_rename_fail", 1);
      return 0;
    }
    metadata_.AddMetric("physical_dedup_count", 1);
    metadata_.AddMetric("physical_dedup_bytes", FileSizeNoThrow(handle.physical_path));
    return 0;
  }

  std::optional<std::string> ChecksumFile(const fs::path& path) const {
    if (config_.checksum != "fnv1a64") {
      return "";
    }
    int fd = open(path.c_str(), O_RDONLY);
    if (fd < 0) {
      return std::nullopt;
    }
    constexpr uint64_t kOffset = 14695981039346656037ULL;
    constexpr uint64_t kPrime = 1099511628211ULL;
    uint64_t hash = kOffset;
    std::vector<unsigned char> buffer(1024 * 1024);
    while (true) {
      ssize_t n = read(fd, buffer.data(), buffer.size());
      if (n < 0) {
        if (errno == EINTR) {
          continue;
        }
        close(fd);
        return std::nullopt;
      }
      if (n == 0) {
        break;
      }
      for (ssize_t i = 0; i < n; ++i) {
        hash ^= buffer[static_cast<size_t>(i)];
        hash *= kPrime;
      }
    }
    close(fd);
    std::ostringstream out;
    out << "fnv1a64:" << std::hex << std::setw(16) << std::setfill('0') << hash;
    return out.str();
  }

  void RecoverIncompleteFiles() {
    for (const auto& meta : metadata_.IncompleteFiles()) {
      if (meta.state == "DELETING_CACHE") {
        FileMeta recovered = meta;
        auto parsed = ParseGpuPath(meta.logical_path);
        if (parsed) {
          const auto [gpu, rel] = *parsed;
          recovered.tier = "remote";
          recovered.backend_id = gpu->remote_backend;
          recovered.physical_path = RemotePath(*gpu, rel);
          recovered.primary_tier = "remote";
          recovered.has_remote_copy = true;
          recovered.local_cache_owner_gpu = -1;
          recovered.replica_state = "REMOTE_ONLY";
          recovered.state = "COMMITTED";
          recovered.last_demoted_at = UnixNowSeconds();
          std::error_code ec;
          fs::remove(meta.physical_path, ec);
          metadata_.Upsert(recovered);
          metadata_.AddMetric("cache_delete_recovered_count", 1);
          continue;
        }
      }
      if (meta.state == "COPYING_TO_REMOTE" || meta.state == "COPYING_TO_LOCAL" ||
          meta.state == "REMOTE_READY" || meta.state == "LOCAL_READY") {
        FileMeta recovered = meta;
        recovered.state = "COMMITTED";
        metadata_.Upsert(recovered);
        metadata_.AddMetric("migration_recovered_count", 1);
        continue;
      }
      std::error_code ec;
      fs::remove(meta.physical_path, ec);
      metadata_.Remove(meta.logical_path);
    }
    for (const auto& gpu : config_.gpus) {
      RemoveTempFiles(gpu.local_root);
      RemoveTempFiles(RemotePath(gpu, ""));
    }
  }

  void RemoveTempFiles(const fs::path& root) const {
    std::error_code ec;
    if (!fs::exists(root, ec)) {
      return;
    }
    for (fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec), end;
         it != end && !ec; it.increment(ec)) {
      const auto filename = it->path().filename().string();
      if (filename.find(config_.temp_suffix) != std::string::npos) {
        fs::remove(it->path(), ec);
      }
    }
  }

  uint64_t StoreHandle(Handle handle) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    uint64_t id = next_handle_++;
    handles_.emplace(id, std::move(handle));
    return id;
  }

  Handle* FindHandle(const fuse_file_info* fi) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    auto it = handles_.find(fi->fh);
    if (it == handles_.end()) {
      return nullptr;
    }
    return &it->second;
  }

  bool IsOpenLogicalPath(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    for (const auto& [_, handle] : handles_) {
      if (handle.logical_path == logical_path) {
        return true;
      }
    }
    return false;
  }

  static void AddDirectoryNames(const fs::path& dir, std::set<std::string>& names) {
    std::error_code ec;
    if (!fs::is_directory(dir, ec)) {
      return;
    }
    for (const auto& entry : fs::directory_iterator(dir, ec)) {
      const auto name = entry.path().filename().string();
      if (name == ".tokenfs-replicas") {
        continue;
      }
      names.insert(name);
    }
  }

  static int StatPhysical(const fs::path& path, struct stat* stbuf) {
    if (lstat(path.c_str(), stbuf) != 0) {
      return -errno;
    }
    return 0;
  }

  using Clock = std::chrono::steady_clock;

  static uint64_t ElapsedMicros(Clock::time_point start) {
    return static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - start)
            .count());
  }

  static std::string LatencyBucket(uint64_t latency_us) {
    if (latency_us <= 100) {
      return "le_100us";
    }
    if (latency_us <= 1000) {
      return "le_1ms";
    }
    if (latency_us <= 10000) {
      return "le_10ms";
    }
    if (latency_us <= 100000) {
      return "le_100ms";
    }
    return "gt_100ms";
  }

  void RecordLatency(const std::string& op, const std::string& tier,
                     uint64_t latency_us) {
    metadata_.AddMetric(op + "_latency_us_total", latency_us);
    metadata_.AddMetric(op + "_" + tier + "_latency_us_total", latency_us);
    metadata_.SetMetricMax(op + "_latency_us_max", latency_us);
    metadata_.SetMetricMax(op + "_" + tier + "_latency_us_max", latency_us);
    const std::string bucket = LatencyBucket(latency_us);
    metadata_.AddMetric(op + "_latency_bucket_" + bucket, 1);
    metadata_.AddMetric(op + "_" + tier + "_latency_bucket_" + bucket, 1);
  }

  void ApplyQos(const Handle& handle, bool write, uint64_t bytes) {
    const uint64_t limit =
        write ? config_.qos_write_iops_per_gpu : config_.qos_read_iops_per_gpu;
    if (limit == 0) {
      metadata_.AddMetric(write ? "qos_foreground_write_ops"
                                : "qos_foreground_read_ops",
                          1);
      return;
    }
    metadata_.AddMetric(write ? "qos_foreground_write_ops"
                              : "qos_foreground_read_ops",
                        1);
    const auto gap = std::chrono::microseconds(
        std::max<uint64_t>(1, 1000000ULL / std::max<uint64_t>(1, limit)));
    const std::string key =
        std::to_string(handle.caller_gpu_id) + (write ? ":fg_write" : ":fg_read");
    Clock::duration delay{};
    {
      std::lock_guard<std::mutex> lock(qos_mu_);
      const auto now = Clock::now();
      auto& next = qos_next_[key];
      if (next > now) {
        delay = next - now;
        next += gap;
      } else {
        next = now + gap;
      }
    }
    if (delay.count() <= 0) {
      return;
    }
    const auto delay_us =
        std::chrono::duration_cast<std::chrono::microseconds>(delay).count();
    metadata_.AddMetric("qos_delay_us_total", static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_delay_ops", 1);
    metadata_.AddMetric("qos_foreground_delay_ops", 1);
    metadata_.AddMetric("qos_foreground_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_gpu" + std::to_string(handle.caller_gpu_id) +
                            "_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_gpu" + std::to_string(handle.caller_gpu_id) +
                            "_delayed_bytes",
                        bytes);
    std::this_thread::sleep_for(delay);
  }

  void ApplyBackgroundQos(int gpu_id, uint64_t bytes,
                          const std::string& activity) {
    metadata_.AddMetric("qos_background_ops", 1);
    metadata_.AddMetric("qos_background_bytes", bytes);
    metadata_.AddMetric("qos_background_" + activity + "_ops", 1);
    metadata_.AddMetric("qos_background_" + activity + "_bytes", bytes);

    Clock::duration delay{};
    if (config_.qos_background_iops_per_gpu > 0) {
      const auto gap = std::chrono::microseconds(std::max<uint64_t>(
          1, 1000000ULL / config_.qos_background_iops_per_gpu));
      const std::string key = std::to_string(gpu_id) + ":bg_op";
      std::lock_guard<std::mutex> lock(qos_mu_);
      const auto now = Clock::now();
      auto& next = qos_next_[key];
      if (next > now) {
        delay = std::max(delay, next - now);
        next += gap;
      } else {
        next = now + gap;
      }
    }
    if (config_.qos_background_mib_per_sec_per_gpu > 0 && bytes > 0) {
      const uint64_t mib = std::max<uint64_t>(1, bytes / 1024 / 1024);
      const uint64_t delay_us =
          mib * 1000000ULL / config_.qos_background_mib_per_sec_per_gpu;
      delay = std::max(
          delay,
          std::chrono::duration_cast<Clock::duration>(
              std::chrono::microseconds(delay_us)));
    }
    if (delay.count() <= 0) {
      return;
    }
    const auto delay_us =
        std::chrono::duration_cast<std::chrono::microseconds>(delay).count();
    metadata_.AddMetric("qos_delay_us_total", static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_delay_ops", 1);
    metadata_.AddMetric("qos_background_delay_ops", 1);
    metadata_.AddMetric("qos_background_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_gpu" + std::to_string(gpu_id) +
                            "_background_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    std::this_thread::sleep_for(delay);
  }

  void MaybeAdaptivePromote(const Handle& handle, uint64_t latency_us) {
    if (!config_.adaptive_migration || handle.tier != "remote" ||
        latency_us < config_.adaptive_remote_promote_us) {
      return;
    }
    auto parsed = ParseGpuPath(handle.logical_path);
    if (!parsed) {
      return;
    }
    const auto [gpu, rel] = *parsed;
    auto existing = metadata_.Get(handle.logical_path);
    if (!existing || existing->tier != "remote" || existing->state != "COMMITTED") {
      return;
    }
    metadata_.AddMetric("adaptive_promote_trigger_count", 1);
    FileMeta meta = *existing;
    if (int rc = PromoteToLocal(*gpu, rel, meta, "adaptive_promote"); rc != 0) {
      metadata_.AddMetric("adaptive_promote_error_count", 1);
    }
  }

  Config config_;
  MetadataStore metadata_;
  std::mutex handles_mu_;
  std::unordered_map<uint64_t, Handle> handles_;
  uint64_t next_handle_ = 1;
  std::mutex prefetch_mu_;
  std::set<std::string> prefetch_inflight_;
  std::mutex qos_mu_;
  std::unordered_map<std::string, Clock::time_point> qos_next_;
};

TokenFS* g_fs = nullptr;

int OpGetAttr(const char* path, struct stat* stbuf, fuse_file_info* fi) {
  return g_fs->GetAttr(path, stbuf, fi);
}

int OpReadDir(const char* path, void* buf, fuse_fill_dir_t filler, off_t offset,
              fuse_file_info* fi, enum fuse_readdir_flags flags) {
  return g_fs->ReadDir(path, buf, filler, offset, fi, flags);
}

int OpMkDir(const char* path, mode_t mode) { return g_fs->MkDir(path, mode); }
int OpRmDir(const char* path) { return g_fs->RmDir(path); }
int OpCreate(const char* path, mode_t mode, fuse_file_info* fi) {
  return g_fs->Create(path, mode, fi);
}
int OpOpen(const char* path, fuse_file_info* fi) { return g_fs->Open(path, fi); }
int OpRead(const char* path, char* buf, size_t size, off_t offset,
           fuse_file_info* fi) {
  return g_fs->Read(path, buf, size, offset, fi);
}
int OpWrite(const char* path, const char* buf, size_t size, off_t offset,
            fuse_file_info* fi) {
  return g_fs->Write(path, buf, size, offset, fi);
}
int OpRelease(const char* path, fuse_file_info* fi) {
  return g_fs->Release(path, fi);
}
int OpFsync(const char* path, int datasync, fuse_file_info* fi) {
  return g_fs->Fsync(path, datasync, fi);
}
int OpFallocate(const char* path, int mode, off_t offset, off_t length,
                fuse_file_info* fi) {
  return g_fs->Fallocate(path, mode, offset, length, fi);
}
int OpTruncate(const char* path, off_t size, fuse_file_info* fi) {
  return g_fs->Truncate(path, size, fi);
}
int OpUnlink(const char* path) { return g_fs->Unlink(path); }
int OpRename(const char* from, const char* to, unsigned int flags) {
  return g_fs->Rename(from, to, flags);
}

uint64_t GiBToBytes(uint64_t gib) { return gib * 1024ULL * 1024ULL * 1024ULL; }
uint64_t MiBToBytes(uint64_t mib) { return mib * 1024ULL * 1024ULL; }

Config LoadConfig(const fs::path& path) {
  YAML::Node root = YAML::LoadFile(path.string());
  Config config;
  config.mount_point =
      root["filesystem"]["mount_point"].as<std::string>("/mnt/tokenfs");
  config.metadata_db = root["filesystem"]["metadata_db"].as<std::string>(
      "/var/lib/tokenfs/metadata/tokenfs.db");
  config.temp_suffix =
      root["filesystem"]["temp_suffix"].as<std::string>(".tokenfs_tmp");
  if (root["policy"] && root["policy"]["checksum"]) {
    config.checksum = root["policy"]["checksum"].as<std::string>("none");
  }
  if (root["policy"] && root["policy"]["local_eviction_policy"]) {
    config.local_eviction_policy =
        root["policy"]["local_eviction_policy"].as<std::string>("value_aware");
  }
  if (root["policy"] && root["policy"]["placement_policy"]) {
    config.placement_policy =
        root["policy"]["placement_policy"].as<std::string>("value_aware");
  }
  if (root["policy"] && root["policy"]["default_recompute_cost"]) {
    config.default_recompute_cost =
        root["policy"]["default_recompute_cost"].as<uint64_t>(10);
  }
  if (root["policy"] && root["policy"]["default_remote_access_cost"]) {
    config.default_remote_access_cost =
        root["policy"]["default_remote_access_cost"].as<uint64_t>(10);
  }
  if (root["policy"] && root["policy"]["value_promote_threshold"]) {
    config.value_promote_threshold =
        root["policy"]["value_promote_threshold"].as<uint64_t>(100);
  }
  if (root["policy"] && root["policy"]["adaptive_migration"]) {
    config.adaptive_migration =
        root["policy"]["adaptive_migration"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["adaptive_remote_promote_us"]) {
    config.adaptive_remote_promote_us =
        root["policy"]["adaptive_remote_promote_us"].as<uint64_t>(10000);
  }
  if (root["policy"] && root["policy"]["qos_read_iops_per_gpu"]) {
    config.qos_read_iops_per_gpu =
        root["policy"]["qos_read_iops_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["qos_write_iops_per_gpu"]) {
    config.qos_write_iops_per_gpu =
        root["policy"]["qos_write_iops_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["qos_background_iops_per_gpu"]) {
    config.qos_background_iops_per_gpu =
        root["policy"]["qos_background_iops_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["qos_background_mib_per_sec_per_gpu"]) {
    config.qos_background_mib_per_sec_per_gpu =
        root["policy"]["qos_background_mib_per_sec_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["affinity_dominant_threshold_x100"]) {
    config.affinity_dominant_threshold_x100 =
        root["policy"]["affinity_dominant_threshold_x100"].as<uint64_t>(70);
  }
  if (root["policy"] && root["policy"]["affinity_shared_threshold_x100"]) {
    config.affinity_shared_threshold_x100 =
        root["policy"]["affinity_shared_threshold_x100"].as<uint64_t>(55);
  }
  if (root["policy"] && root["policy"]["affinity_short_window_sec"]) {
    config.affinity_short_window_sec =
        root["policy"]["affinity_short_window_sec"].as<uint64_t>(300);
  }
  if (root["policy"] && root["policy"]["affinity_long_window_sec"]) {
    config.affinity_long_window_sec =
        root["policy"]["affinity_long_window_sec"].as<uint64_t>(3600);
  }
  if (root["policy"] && root["policy"]["affinity_trend_min_reads"]) {
    config.affinity_trend_min_reads =
        root["policy"]["affinity_trend_min_reads"].as<uint64_t>(3);
  }
  if (root["policy"] && root["policy"]["affinity_hot_read_threshold"]) {
    config.affinity_hot_read_threshold =
        root["policy"]["affinity_hot_read_threshold"].as<uint64_t>(4);
  }
  if (root["policy"] && root["policy"]["affinity_warm_read_threshold"]) {
    config.affinity_warm_read_threshold =
        root["policy"]["affinity_warm_read_threshold"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["max_local_replicas_per_file"]) {
    config.max_local_replicas_per_file =
        root["policy"]["max_local_replicas_per_file"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["affinity_replica_cooldown_sec"]) {
    config.affinity_replica_cooldown_sec =
        root["policy"]["affinity_replica_cooldown_sec"].as<uint64_t>(30);
  }
  if (root["policy"] && root["policy"]["affinity_replica_min_residency_sec"]) {
    config.affinity_replica_min_residency_sec =
        root["policy"]["affinity_replica_min_residency_sec"].as<uint64_t>(120);
  }
  if (root["policy"] && root["policy"]["cross_gpu_local_cache"]) {
    config.cross_gpu_local_cache =
        root["policy"]["cross_gpu_local_cache"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["physical_dedup"]) {
    config.physical_dedup = root["policy"]["physical_dedup"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["promote_on_read"]) {
    config.promote_on_read = root["policy"]["promote_on_read"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["promote_read_threshold"]) {
    config.promote_read_threshold =
        root["policy"]["promote_read_threshold"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["prefetch_on_read"]) {
    config.prefetch_on_read = root["policy"]["prefetch_on_read"].as<bool>(false);
  }

  for (const auto& item : root["backends"]) {
    BackendConfig backend;
    backend.id = item["id"].as<std::string>();
    backend.type = item["type"].as<std::string>("directory");
    backend.root = item["root"].as<std::string>();
    config.backends.emplace(backend.id, backend);
  }

  for (const auto& item : root["gpus"]) {
    GpuConfig gpu;
    gpu.gpu_id = item["gpu_id"].as<int>();
    gpu.logical_root = item["logical_root"].as<std::string>();
    gpu.local_root = item["local_root"].as<std::string>();
    if (item["local_quota_mib"]) {
      gpu.local_quota_bytes = MiBToBytes(item["local_quota_mib"].as<uint64_t>());
    } else {
      gpu.local_quota_bytes = GiBToBytes(item["local_quota_gib"].as<uint64_t>());
    }
    gpu.remote_backend = item["remote_backend"].as<std::string>();
    config.gpus.push_back(std::move(gpu));
  }
  return config;
}

std::vector<char*> BuildFuseArgv(const std::vector<std::string>& args,
                                 std::vector<std::string>& storage) {
  std::vector<char*> argv;
  storage = args;
  argv.reserve(storage.size());
  for (auto& arg : storage) {
    argv.push_back(arg.data());
  }
  return argv;
}

}  // namespace

int main(int argc, char* argv[]) {
  fs::path config_path = "config/tokenfs.dev.yaml";
  std::vector<std::string> fuse_args;
  fuse_args.emplace_back(argv[0]);

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--config" && i + 1 < argc) {
      config_path = argv[++i];
    } else {
      fuse_args.push_back(arg);
    }
  }

  try {
    Config config = LoadConfig(config_path);
    if (fuse_args.size() == 1) {
      fuse_args.push_back(config.mount_point.string());
    }
    auto fs = std::make_unique<TokenFS>(std::move(config));
    fs->Init();
    g_fs = fs.get();

    fuse_operations ops{};
    ops.getattr = OpGetAttr;
    ops.readdir = OpReadDir;
    ops.mkdir = OpMkDir;
    ops.rmdir = OpRmDir;
    ops.create = OpCreate;
    ops.open = OpOpen;
    ops.read = OpRead;
    ops.write = OpWrite;
    ops.release = OpRelease;
    ops.fsync = OpFsync;
    ops.fallocate = OpFallocate;
    ops.truncate = OpTruncate;
    ops.unlink = OpUnlink;
    ops.rename = OpRename;

    std::vector<std::string> argv_storage;
    auto fuse_argv = BuildFuseArgv(fuse_args, argv_storage);
    return fuse_main(static_cast<int>(fuse_argv.size()), fuse_argv.data(), &ops,
                     nullptr);
  } catch (const std::exception& ex) {
    std::cerr << "tokenfs: " << ex.what() << "\n";
    return 1;
  }
}
