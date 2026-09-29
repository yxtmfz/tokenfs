#pragma once
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <deque>
#include <iomanip>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <sstream>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <unistd.h>

// Bounded immutable captures. Optional LRU retention shares the SAME byte budget
// with active readers/copies; admission and copy completion do not set lifetime.
class ReadFillPool {
 public:
  class Buffer;
 private:
  struct Budget {
    std::mutex mu;
    uint64_t used=0,peak=0;
    std::unordered_map<std::string,std::weak_ptr<Buffer>> paths;
  };
 public:
  static uint64_t NowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  class Buffer {
   public:
    Buffer(std::shared_ptr<Budget> budget,std::string path,const struct stat& source,
           const struct stat& anchor,std::string canonical)
        :budget_(std::move(budget)),path_(std::move(path)),source_(source),anchor_(anchor),
         canonical_(std::move(canonical)),data_(source.st_size) {}
    ~Buffer(){std::lock_guard<std::mutex> lock(budget_->mu);budget_->used-=data_.size();budget_->paths.erase(path_);}
    // Returns true exactly once, only when the whole source has been captured.
    bool Append(off_t offset,const char* bytes,size_t count,int fd) {
      const auto started=NowNs();std::lock_guard<std::mutex> lock(mu_);
      if(dispatched_ || invalid_)return false;
      if(offset<0 || uint64_t(offset)!=filled_ || count>data_.size()-filled_) {
        invalid_=true;return false;
      }
      if(count)std::memcpy(data_.data()+filled_,bytes,count);
      filled_+=count;
      if(filled_==data_.size()) {
        struct stat current{};
        if(fstat(fd,&current)!=0 || !SameSource(current) ||
           (!canonical_.empty() && (stat(canonical_.c_str(),&current)!=0 || !SameAnchor(current)))) {
          invalid_=true;return false;
        }
        dispatched_=true;
      }
      capture_ns_+=NowNs()-started;
      return dispatched_;
    }
    void Invalidate(){std::lock_guard<std::mutex> lock(mu_);if(!dispatched_)invalid_=true;}
    bool Dispatched() const {std::lock_guard<std::mutex> lock(mu_);return dispatched_;}
    bool Matches(const std::string& source,uint64_t size) const {
      std::lock_guard<std::mutex> lock(mu_);struct stat current{};
      return dispatched_ && !invalid_ && size==data_.size() &&
        stat(source.c_str(),&current)==0 && SameAnchor(current);
    }
    bool MatchesFd(int fd) const {
      std::lock_guard<std::mutex> lock(mu_);struct stat current{};
      return dispatched_ && !invalid_ && fstat(fd,&current)==0 && SameAnchor(current);
    }
    // Only complete immutable bytes can be borrowed. A checked copy prevents
    // source changes, partial data and invalid offsets from leaking to readers.
    ssize_t ReadCaptured(int fd,char* out,size_t count,off_t offset) const {
      std::lock_guard<std::mutex> lock(mu_);struct stat current{};
      if(!dispatched_ || invalid_ || fstat(fd,&current)!=0 || !SameAnchor(current))return -ESTALE;
      if(offset<0)return -EINVAL;
      if(uint64_t(offset)>=data_.size())return 0;
      const auto n=std::min(count,data_.size()-size_t(offset));
      if(n)std::memcpy(out,data_.data()+offset,n);
      return static_cast<ssize_t>(n);
    }
    void AddCaptureNs(uint64_t n){std::lock_guard<std::mutex> lock(mu_);capture_ns_+=n;}
    uint64_t CaptureUs() const {std::lock_guard<std::mutex> lock(mu_);return (capture_ns_+999)/1000;}
    // Accessed only after Append has published a complete, immutable buffer.
    const std::vector<char>& Data() const{return data_;}
    std::string Checksum() const {
      uint64_t hash=14695981039346656037ULL;
      for(unsigned char c:data_){hash^=c;hash*=1099511628211ULL;}
      std::ostringstream out;out<<"fnv1a64:"<<std::hex<<std::setw(16)<<std::setfill('0')<<hash;
      return out.str();
    }
   private:
    static bool SameIdentity(const struct stat& s,const struct stat& original) {
      if(s.st_dev!=original.st_dev || s.st_ino!=original.st_ino || s.st_size!=original.st_size)return false;
#ifdef __APPLE__
      return s.st_mtimespec.tv_sec==original.st_mtimespec.tv_sec && s.st_mtimespec.tv_nsec==original.st_mtimespec.tv_nsec &&
        s.st_ctimespec.tv_sec==original.st_ctimespec.tv_sec && s.st_ctimespec.tv_nsec==original.st_ctimespec.tv_nsec;
#else
      return s.st_mtim.tv_sec==original.st_mtim.tv_sec && s.st_mtim.tv_nsec==original.st_mtim.tv_nsec &&
        s.st_ctim.tv_sec==original.st_ctim.tv_sec && s.st_ctim.tv_nsec==original.st_ctim.tv_nsec;
#endif
    }
    bool SameSource(const struct stat& s) const{return SameIdentity(s,source_);}
    bool SameAnchor(const struct stat& s) const{return SameIdentity(s,anchor_);}
    std::shared_ptr<Budget> budget_;std::string path_;struct stat source_{},anchor_{};std::string canonical_;
    std::vector<char> data_;mutable std::mutex mu_;
    size_t filled_=0;bool invalid_=false,dispatched_=false;uint64_t capture_ns_=0;
  };
  explicit ReadFillPool(uint64_t limit,bool retain=false):limit_(limit),budget_(std::make_shared<Budget>()),retain_(retain){}
  void Retain(const std::shared_ptr<Buffer>& buffer) {
    if(!retain_ || !buffer || !buffer->Dispatched())return;
    std::lock_guard<std::mutex> lock(retained_mu_);
    std::erase(retained_,buffer);retained_.push_back(buffer);
  }
  std::shared_ptr<Buffer> Acquire(const std::string& path,int fd,uint64_t size,const std::string& canonical="") {
    const auto started=NowNs();struct stat source{};
    if(size==0 || size>limit_ || fstat(fd,&source)!=0 || !S_ISREG(source.st_mode) ||
        source.st_size<0 || uint64_t(source.st_size)!=size)return {};
    struct stat anchor=source;
    if(!canonical.empty() && (stat(canonical.c_str(),&anchor)!=0 || !S_ISREG(anchor.st_mode) || anchor.st_size!=source.st_size))return {};
    // Drop only unpinned retained captures. Active readers/copies remain charged
    // even after LRU removal, so pressure can safely reject a new allocation.
    std::lock_guard<std::mutex> retained_lock(retained_mu_);
    while(size>limit_-UsedBytes()) {
      auto it=std::find_if(retained_.begin(),retained_.end(),[](const auto& b){return b.use_count()==1;});
      if(it==retained_.end())return {};
      retained_.erase(it); // Destructor acquires budget_->mu; do not hold it here.
    }
    std::lock_guard<std::mutex> lock(budget_->mu);
    if(size>limit_-budget_->used || budget_->paths.count(path))return {};
    // Allocate before charging: an allocation failure leaves the budget intact.
    std::shared_ptr<Buffer> buffer;
    try {budget_->paths.emplace(path,std::weak_ptr<Buffer>{});buffer=std::make_shared<Buffer>(budget_,path,source,anchor,canonical);budget_->paths.at(path)=buffer;}
    catch(const std::bad_alloc&){budget_->paths.erase(path);return {};}
    budget_->used+=size;budget_->peak=std::max(budget_->peak,budget_->used);
    buffer->AddCaptureNs(NowNs()-started);return buffer;
  }
  std::shared_ptr<Buffer> FindComplete(const std::string& path,const std::string& source,uint64_t size) {
    std::shared_ptr<Buffer> found;
    {
      std::lock_guard<std::mutex> lock(budget_->mu);
      const auto it=budget_->paths.find(path);
      if(it!=budget_->paths.end())found=it->second.lock();
    }
    // Never destroy the last buffer while holding its budget mutex.
    if(found && found->Matches(source,size)) {Retain(found);return found;}
    if(found && retain_) {
      std::lock_guard<std::mutex> lock(retained_mu_);std::erase(retained_,found);
    }
    return {};
  }
  uint64_t PeakBytes() const {std::lock_guard<std::mutex> lock(budget_->mu);return budget_->peak;}
  uint64_t UsedBytes() const {std::lock_guard<std::mutex> lock(budget_->mu);return budget_->used;}
 private:
  uint64_t limit_;std::shared_ptr<Budget> budget_;bool retain_;
  std::mutex retained_mu_;
  // Owned by the pool, not Budget: Buffer -> Budget never forms a strong cycle.
  std::deque<std::shared_ptr<Buffer>> retained_;
};
