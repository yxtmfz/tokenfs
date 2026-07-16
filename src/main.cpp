#define FUSE_USE_VERSION 35

#include <fuse3/fuse.h>
#include <sqlite3.h>
#include <yaml-cpp/yaml.h>

#include <cerrno>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <string>
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
  std::string state = "COMMITTED";
};

struct Handle {
  int fd = -1;
  std::string logical_path;
  int gpu_id = -1;
  std::string tier;
  std::string backend_id;
  fs::path physical_path;
  int flags = 0;
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
         "state TEXT NOT NULL,"
         "created_at INTEGER NOT NULL,"
         "updated_at INTEGER NOT NULL,"
         "last_access_at INTEGER"
         ");");
  }

  std::optional<FileMeta> Get(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    const char* sql =
        "SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,state "
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
    meta.state = ColumnText(stmt, 6);
    sqlite3_finalize(stmt);
    return meta;
  }

  void Upsert(const FileMeta& meta) {
    std::lock_guard<std::mutex> lock(mu_);
    const auto now = UnixNow();
    const char* sql =
        "INSERT INTO files(logical_path,gpu_id,tier,backend_id,physical_path,"
        "size_bytes,state,created_at,updated_at,last_access_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(logical_path) DO UPDATE SET "
        "gpu_id=excluded.gpu_id,"
        "tier=excluded.tier,"
        "backend_id=excluded.backend_id,"
        "physical_path=excluded.physical_path,"
        "size_bytes=excluded.size_bytes,"
        "state=excluded.state,"
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
    sqlite3_bind_text(stmt, 7, meta.state.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 8, now);
    sqlite3_bind_int64(stmt, 9, now);
    sqlite3_bind_int64(stmt, 10, now);
    StepDone(stmt);
  }

  void Remove(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM files WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  std::vector<FileMeta> ChildrenUnder(const std::string& logical_dir) {
    std::lock_guard<std::mutex> lock(mu_);
    std::string prefix = logical_dir;
    if (prefix != "/" && prefix.back() != '/') {
      prefix += "/";
    }
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,state "
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
      meta.state = ColumnText(stmt, 6);
      out.push_back(std::move(meta));
    }
    sqlite3_finalize(stmt);
    return out;
  }

 private:
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
    fi->fh = StoreHandle({fd, path, gpu->gpu_id, meta.tier, meta.backend_id,
                          meta.physical_path, fi->flags});
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
        meta = {path, gpu->gpu_id, "local", "local", local,
                FileSizeNoThrow(local), "COMMITTED"};
      } else {
        auto remote = RemotePath(*gpu, rel);
        if (!fs::exists(remote)) {
          return -ENOENT;
        }
        meta = {path, gpu->gpu_id, "remote", gpu->remote_backend, remote,
                FileSizeNoThrow(remote), "COMMITTED"};
      }
      metadata_.Upsert(meta);
    }
    int fd = open(meta.physical_path.c_str(), fi->flags);
    if (fd < 0) {
      return -errno;
    }
    fi->fh = StoreHandle({fd, path, gpu->gpu_id, meta.tier, meta.backend_id,
                          meta.physical_path, fi->flags});
    return 0;
  }

  int Read(const char*, char* buf, size_t size, off_t offset,
           fuse_file_info* fi) {
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    ssize_t n = pread(handle->fd, buf, size, offset);
    if (n < 0) {
      return -errno;
    }
    return static_cast<int>(n);
  }

  int Write(const char*, const char* buf, size_t size, off_t offset,
            fuse_file_info* fi) {
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    if (int rc = SpillIfNeeded(*handle, static_cast<uint64_t>(offset + size));
        rc != 0) {
      return rc;
    }
    ssize_t n = pwrite(handle->fd, buf, size, offset);
    if (n < 0) {
      return -errno;
    }
    UpdateHandleMeta(*handle);
    return static_cast<int>(n);
  }

  int Release(const char*, fuse_file_info* fi) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    auto it = handles_.find(fi->fh);
    if (it == handles_.end()) {
      return 0;
    }
    if (it->second.fd >= 0) {
      close(it->second.fd);
    }
    handles_.erase(it);
    return 0;
  }

  int Fsync(const char*, int datasync, fuse_file_info* fi) {
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    int rc = datasync ? fdatasync(handle->fd) : fsync(handle->fd);
    if (rc != 0) {
      return -errno;
    }
    UpdateHandleMeta(*handle);
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
      UpdateHandleMeta(*handle);
      return 0;
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

  static uint64_t FileSizeNoThrow(const fs::path& path) {
    std::error_code ec;
    auto size = fs::file_size(path, ec);
    return ec ? 0 : static_cast<uint64_t>(size);
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

  FileMeta SelectNewFile(const GpuConfig& gpu, const fs::path& rel,
                         const std::string& logical_path) const {
    const uint64_t used = DirectoryBytes(gpu.local_root);
    if (used < gpu.local_quota_bytes) {
      return {logical_path, gpu.gpu_id, "local", "local", gpu.local_root / rel,
              0, "COMMITTED"};
    }
    return {logical_path, gpu.gpu_id, "remote", gpu.remote_backend,
            RemotePath(gpu, rel), 0, "COMMITTED"};
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

    auto parsed = ParseGpuPath(handle.logical_path);
    if (!parsed) {
      return -EINVAL;
    }
    fs::path remote = RemotePath(*gpu, parsed->second);
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
    handle.fd = open(handle.physical_path.c_str(), handle.flags);
    if (handle.fd < 0) {
      return -errno;
    }
    UpdateHandleMeta(handle);
    return 0;
  }

  void UpdateHandleMeta(const Handle& handle) {
    FileMeta meta;
    meta.logical_path = handle.logical_path;
    meta.gpu_id = handle.gpu_id;
    meta.tier = handle.tier;
    meta.backend_id = handle.backend_id;
    meta.physical_path = handle.physical_path;
    meta.size_bytes = FileSizeNoThrow(handle.physical_path);
    meta.state = "COMMITTED";
    metadata_.Upsert(meta);
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

  static void AddDirectoryNames(const fs::path& dir, std::set<std::string>& names) {
    std::error_code ec;
    if (!fs::is_directory(dir, ec)) {
      return;
    }
    for (const auto& entry : fs::directory_iterator(dir, ec)) {
      names.insert(entry.path().filename().string());
    }
  }

  static int StatPhysical(const fs::path& path, struct stat* stbuf) {
    if (lstat(path.c_str(), stbuf) != 0) {
      return -errno;
    }
    return 0;
  }

  Config config_;
  MetadataStore metadata_;
  std::mutex handles_mu_;
  std::unordered_map<uint64_t, Handle> handles_;
  uint64_t next_handle_ = 1;
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
int OpTruncate(const char* path, off_t size, fuse_file_info* fi) {
  return g_fs->Truncate(path, size, fi);
}
int OpUnlink(const char* path) { return g_fs->Unlink(path); }
int OpRename(const char* from, const char* to, unsigned int flags) {
  return g_fs->Rename(from, to, flags);
}

uint64_t GiBToBytes(uint64_t gib) { return gib * 1024ULL * 1024ULL * 1024ULL; }

Config LoadConfig(const fs::path& path) {
  YAML::Node root = YAML::LoadFile(path.string());
  Config config;
  config.mount_point =
      root["filesystem"]["mount_point"].as<std::string>("/mnt/tokenfs");
  config.metadata_db = root["filesystem"]["metadata_db"].as<std::string>(
      "/var/lib/tokenfs/metadata/tokenfs.db");
  config.temp_suffix =
      root["filesystem"]["temp_suffix"].as<std::string>(".tokenfs_tmp");

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
    gpu.local_quota_bytes = GiBToBytes(item["local_quota_gib"].as<uint64_t>());
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
