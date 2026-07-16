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
