cmake_minimum_required (VERSION 3.13)

project(someipy_test_apps)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14")

find_package(vsomeip3 CONFIG REQUIRED)

set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/install")

function(create_test_target target_name)

    add_executable(${target_name} ${target_name}/${target_name}.cpp)
    target_link_libraries(${target_name} ${VSOMEIP_LIBRARIES} pthread)

    install(TARGETS ${target_name}
        RUNTIME DESTINATION ${target_name})

    file(GLOB ADDITIONAL_FILES "${CMAKE_SOURCE_DIR}/${target_name}/*.json" "${CMAKE_SOURCE_DIR}/${target_name}/*.sh")
    install(FILES ${ADDITIONAL_FILES} DESTINATION ${target_name})
    
endfunction()

# The same app can be used for UDP and TCP for the "send_events" example app
create_test_target("send_events")

create_test_target("receive_events_udp")
