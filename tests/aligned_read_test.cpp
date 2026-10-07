#include "../src/aligned_read.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <fcntl.h>
#include <random>
#include <string>
#include <vector>

int main() {
  namespace fs=std::filesystem;
  const auto root=fs::temp_directory_path()/("tokenfs-aligned-test-"+std::to_string(getpid()));
  fs::create_directory(root);const auto path=root/"source";
  constexpr size_t mib=1024*1024;
  std::string payload(2*mib,'\0');
  for(size_t i=0;i<payload.size();++i)payload[i]=char((i*17+i/4096)%251);
  std::ofstream(path,std::ios::binary).write(payload.data(),payload.size());
  const int writer=open(path.c_str(),O_RDWR);assert(writer>=0);
  int flags=O_RDONLY;
#ifdef O_DIRECT
  flags|=O_DIRECT;
#endif
  int fd=open(path.c_str(),flags);assert(fd>=0);
  std::vector<char> output(2*mib);AlignedReadTail::Stats stats;
  {
    AlignedReadTail tail;size_t offset=0;uint64_t ops=0,bytes=0,hits=0,logical=0;
    // Actual FUSE fragmentation from the frozen diagnostic. No read-ahead,
    // no extra shared capture: the two 48-byte tails already arrived on disk.
    for(size_t amount:{mib-48,size_t(48),mib-48,size_t(48),mib}) {
      const auto n=tail.Read(fd,output.data(),amount,offset,stats,true);
      assert(n>=0 && size_t(n)==std::min(amount,payload.size()-offset));
      assert(std::string(output.data(),size_t(n))==payload.substr(offset,size_t(n)));
      offset+=size_t(n);logical+=size_t(n);ops+=stats.pread_ops;bytes+=stats.pread_bytes;hits+=stats.tail_hits;
      assert(tail.RetainedBytes()<4096);
    }
    assert(logical==2*mib && ops==3 && bytes==2*mib && hits==2);
    // The unoptimized aligned operations reread the final page twice.
    assert(5-ops==2 && 2*mib+2*4096-bytes==8192);
  }
  {
    AlignedReadTail tail;
    assert(tail.Read(fd,output.data(),mib-48,0,stats)==ssize_t(mib-48));
    assert(tail.RetainedBytes()==48);
    assert(tail.Read(fd,output.data(),20,mib-48,stats)==20 && stats.tail_hits==1);
    assert(std::string(output.data(),20)==payload.substr(mib-48,20));
    assert(tail.Read(fd,output.data(),28,mib-28,stats)==28 && stats.tail_hits==1);
    assert(std::string(output.data(),28)==payload.substr(mib-28,28));
    assert(tail.RetainedBytes()==0);
    // Overlap, gap and partial coverage fall back to real aligned reads.
    for(auto [offset,amount]:std::vector<std::pair<off_t,size_t>>{{7,19},{7,19},{50,12},{61,5000},{8193,6000},{mib-60,90}}) {
      assert(tail.Read(fd,output.data(),amount,offset,stats)==ssize_t(amount));
      assert(stats.pread_ops==1 && stats.tail_hits==0);
      assert(std::string(output.data(),amount)==payload.substr(size_t(offset),amount));
    }
  }
  {
    AlignedReadTail tail;std::mt19937 random(75001);
    for(size_t trial=0;trial<500;++trial) {
      const size_t offset=random()%(payload.size()+8192);
      const size_t amount=1+random()%65536;
      const size_t expected=offset<payload.size()?std::min(amount,payload.size()-offset):0;
      const auto n=tail.Read(fd,output.data(),amount,off_t(offset),stats);
      assert(n==ssize_t(expected));
      assert(std::string(output.data(),expected)==(offset<payload.size()?payload.substr(offset,expected):std::string{}));
      assert(tail.RetainedBytes()<4096);
    }
  }
  {
    AlignedReadTail tail;
    assert(tail.Read(fd,output.data(),mib-48,0,stats)==ssize_t(mib-48));
    const std::string changed(48,'!');assert(pwrite(writer,changed.data(),changed.size(),mib-48)==48);
    // Force distinct identity even on filesystems with coarse timestamps.
    struct stat st{};assert(fstat(writer,&st)==0);
    const timespec times[2]={{st.st_atime+1,0},{st.st_mtime+1,0}};
    assert(futimens(writer,times)==0);
    assert(tail.Read(fd,output.data(),48,mib-48,stats)==48);
    assert(stats.pread_ops==1 && !stats.tail_hits && stats.invalidations==1);
    assert(std::string(output.data(),48)==changed);
    payload.replace(mib-48,48,changed);
    assert(tail.Read(fd,output.data(),mib-48,0,stats)==ssize_t(mib-48));
    assert(ftruncate(writer,mib-40)==0);
    assert(tail.Read(fd,output.data(),48,mib-48,stats)==8 && stats.pread_ops==1);
    assert(std::string(output.data(),8)==payload.substr(mib-48,8));
    assert(tail.Read(fd,output.data(),48,mib-40,stats)==0 && !stats.tail_hits);
  }
  {
    AlignedReadTail tail;
    assert(tail.Read(fd,output.data(),64,0,stats)==64);
    const auto replacement=root/"replacement";
    const std::string replacement_data(4096,'?');
    std::ofstream(replacement,std::ios::binary).write(replacement_data.data(),replacement_data.size());
    int other=open(replacement.c_str(),flags);assert(other>=0);
    assert(tail.Read(other,output.data(),64,64,stats)==64 && stats.pread_ops==1 && !stats.tail_hits);
    assert(std::string(output.data(),64)==std::string(64,'?'));close(other);
    assert(tail.Read(-1,output.data(),64,128,stats)==-1 && errno==EBADF);
    assert(tail.Read(fd,output.data(),0,0,stats)==0 && !stats.pread_ops);
    assert(tail.Read(fd,output.data(),1,-1,stats)==-1 && errno==EINVAL);
    assert(tail.Read(fd,output.data(),std::numeric_limits<size_t>::max(),0,stats)==-1 && errno==EINVAL);
    assert(tail.Read(fd,output.data(),4096,std::numeric_limits<off_t>::max(),stats)==-1 && errno==EINVAL);
  }
  close(fd);close(writer);fs::remove_all(root);
}
