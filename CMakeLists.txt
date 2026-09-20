cmake_minimum_required(VERSION 3.20)
project(tokenfs LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(FUSE3 REQUIRED fuse3)
find_package(yaml-cpp REQUIRED)
find_package(SQLite3 REQUIRED)

add_executable(tokenfs
  src/main.cpp
)

target_include_directories(tokenfs PRIVATE
  ${FUSE3_INCLUDE_DIRS}
)

target_compile_options(tokenfs PRIVATE
  ${FUSE3_CFLAGS_OTHER}
  -Wall
  -Wextra
  -Wpedantic
)

target_link_libraries(tokenfs PRIVATE
  ${FUSE3_LIBRARIES}
  yaml-cpp
  SQLite::SQLite3
)

include(CTest)
if(BUILD_TESTING)
  add_executable(policy_metadata_test tests/policy_metadata_test.cpp)
  target_include_directories(policy_metadata_test PRIVATE ${FUSE3_INCLUDE_DIRS})
  target_compile_options(policy_metadata_test PRIVATE ${FUSE3_CFLAGS_OTHER} -UNDEBUG)
  target_link_libraries(policy_metadata_test PRIVATE ${FUSE3_LIBRARIES} yaml-cpp SQLite::SQLite3)
  add_test(NAME policy_metadata COMMAND policy_metadata_test)
  add_executable(measured_policy_test tests/measured_policy_test.cpp)
  target_compile_options(measured_policy_test PRIVATE -UNDEBUG)
  add_test(NAME measured_policy COMMAND measured_policy_test)
endif()
