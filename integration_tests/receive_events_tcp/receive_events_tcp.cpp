#include <chrono>
#include <condition_variable>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>
#include <mutex>

#include <vsomeip/vsomeip.hpp>

#define SAMPLE_SERVICE_ID 0x1234
#define SAMPLE_INSTANCE_ID 0x5678
#define SAMPLE_EVENTGROUP_ID 0x0321
#define SAMPLE_EVENT_ID 0x0123

std::shared_ptr<vsomeip::payload> payload_;
std::shared_ptr<vsomeip::application> app_;
std::set<vsomeip::eventgroup_t> its_groups;
        

void offer() {
    app_->offer_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 1, 0);
    app_->offer_event(
                SAMPLE_SERVICE_ID,
                SAMPLE_INSTANCE_ID,
                SAMPLE_EVENT_ID,
                its_groups,
                vsomeip::event_type_e::ET_EVENT, std::chrono::milliseconds::zero(),
                false, true, nullptr, vsomeip::reliability_type_e::RT_RELIABLE);
    
    
}

void stop_offer() {
    app_->stop_offer_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
}

void run() {
    std::this_thread::sleep_for(std::chrono::milliseconds(3000));

    vsomeip::byte_t its_data[10];
    uint32_t its_size = 1;
    uint32_t loop_counter = 0;

    while (true) {
        for (uint32_t i = 0; i < its_size; ++i) {
            its_data[i] = static_cast<uint8_t>((loop_counter + i) % 255);
        }
        loop_counter++;
        
        payload_->set_data(its_data, its_size);
        std::cout << "Setting event (Length=" << std::dec << its_size << ")." << std::endl;
        app_->notify(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, SAMPLE_EVENT_ID, payload_);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
}
        
int main(int argc, char **argv) {
    its_groups.insert(SAMPLE_EVENTGROUP_ID);

    app_ = vsomeip::runtime::get()->create_application("Hello");
    app_->init();
    payload_ = vsomeip::runtime::get()->create_payload();
    offer();
    std::thread receiver(run);
    app_->start();
}