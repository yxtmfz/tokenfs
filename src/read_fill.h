#pragma once
#include <algorithm>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <memory>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <unistd.h>

// Transient capture only, never a readable cache. Complete immutable-source
// reads can supply a normal verified cache commit without rereading the source.
class ReadFillPool {
  struct Budget {
    std::mutex mu;
    uint64_t used=0,peak=0;
    std::set<std::string> paths;
  };
 public:
  static uint64_t NowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
  }
  class Buffer {
   public:
    Buffer(std::shared_ptr<Budget> budget,std::string path,const struct stat& source)
        :budget_(std::move(budget)),path_(std::move(path)),source_(source),data_(source.st_size) {}
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
        if(fstat(fd,&current)!=0 || !SameSource(current)){invalid_=true;return false;}
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
        stat(source.c_str(),&current)==0 && SameSource(current);
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
    bool SameSource(const struct stat& s) const {
      if(s.st_dev!=source_.st_dev || s.st_ino!=source_.st_ino || s.st_size!=source_.st_size)return false;
#ifdef __APPLE__
      return s.st_mtimespec.tv_sec==source_.st_mtimespec.tv_sec && s.st_mtimespec.tv_nsec==source_.st_mtimespec.tv_nsec &&
        s.st_ctimespec.tv_sec==source_.st_ctimespec.tv_sec && s.st_ctimespec.tv_nsec==source_.st_ctimespec.tv_nsec;
#else
      return s.st_mtim.tv_sec==source_.st_mtim.tv_sec && s.st_mtim.tv_nsec==source_.st_mtim.tv_nsec &&
        s.st_ctim.tv_sec==source_.st_ctim.tv_sec && s.st_ctim.tv_nsec==source_.st_ctim.tv_nsec;
#endif
    }
    std::shared_ptr<Budget> budget_;std::string path_;struct stat source_{};
    std::vector<char> data_;mutable std::mutex mu_;
    size_t filled_=0;bool invalid_=false,dispatched_=false;uint64_t capture_ns_=0;
  };
  explicit ReadFillPool(uint64_t limit):limit_(limit),budget_(std::make_shared<Budget>()){}
  std::shared_ptr<Buffer> Acquire(const std::string& path,int fd,uint64_t size) {
    const auto started=NowNs();struct stat source{};
    if(size==0 || size>limit_ || fstat(fd,&source)!=0 || !S_ISREG(source.st_mode) ||
        source.st_size<0 || uint64_t(source.st_size)!=size)return {};
    std::lock_guard<std::mutex> lock(budget_->mu);
    if(size>limit_-budget_->used || budget_->paths.count(path))return {};
    // Allocate before charging: an allocation failure leaves the budget intact.
    std::shared_ptr<Buffer> buffer;
    try {budget_->paths.insert(path);buffer=std::make_shared<Buffer>(budget_,path,source);}
    catch(const std::bad_alloc&){budget_->paths.erase(path);return {};}
    budget_->used+=size;budget_->peak=std::max(budget_->peak,budget_->used);
    buffer->AddCaptureNs(NowNs()-started);return buffer;
  }
  uint64_t PeakBytes() const {std::lock_guard<std::mutex> lock(budget_->mu);return budget_->peak;}
  uint64_t UsedBytes() const {std::lock_guard<std::mutex> lock(budget_->mu);return budget_->used;}
 private:uint64_t limit_;std::shared_ptr<Budget> budget_;
};
