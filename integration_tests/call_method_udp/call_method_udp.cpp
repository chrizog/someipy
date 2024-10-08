#include <csignal>
#include <chrono>
#include <condition_variable>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>

#include <vsomeip/vsomeip.hpp>

#define SAMPLE_SERVICE_ID 0x1234
#define SAMPLE_INSTANCE_ID 0x5678
#define SAMPLE_METHOD_ID 0x0123


class service_sample {
public:
    service_sample(bool _use_static_routing) :
            app_(vsomeip::runtime::get()->create_application("Hello")),
            is_registered_(false),
            use_static_routing_(_use_static_routing),
            blocked_(false),
            running_(true),
            offer_thread_(std::bind(&service_sample::run, this)) {
    }

    bool init() {
        std::lock_guard<std::mutex> its_lock(mutex_);

        if (!app_->init()) {
            std::cerr << "Couldn't initialize application" << std::endl;
            return false;
        }
        app_->register_state_handler(
                std::bind(&service_sample::on_state, this,
                        std::placeholders::_1));
        app_->register_message_handler(
                SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, SAMPLE_METHOD_ID,
                std::bind(&service_sample::on_message, this,
                        std::placeholders::_1));
        return true;
    }

    void start() {
        app_->start();
    }

    void stop() {
        running_ = false;
        blocked_ = true;
        app_->clear_all_handler();
        stop_offer();
        condition_.notify_one();
        if (std::this_thread::get_id() != offer_thread_.get_id()) {
            if (offer_thread_.joinable()) {
                offer_thread_.join();
            }
        } else {
            offer_thread_.detach();
        }
        app_->stop();
    }

    void offer() {
        app_->offer_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
    }

    void stop_offer() {
        app_->stop_offer_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
    }

    void on_state(vsomeip::state_type_e _state) {
        std::cout << "Application " << app_->get_name() << " is "
                << (_state == vsomeip::state_type_e::ST_REGISTERED ?
                        "registered." : "deregistered.")
                << std::endl;

        if (_state == vsomeip::state_type_e::ST_REGISTERED) {
            if (!is_registered_) {
                is_registered_ = true;
                blocked_ = true;
                condition_.notify_one();
            }
        } else {
            is_registered_ = false;
        }
    }

    void on_message(const std::shared_ptr<vsomeip::message> &_request) {
        // Log the current time.
        auto now = std::chrono::system_clock::now();
        auto now_time_t = std::chrono::system_clock::to_time_t(now);
        auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                now.time_since_epoch()).count();
        auto now_ms_remainder = now_ms % 1000;
        auto now_tm = std::localtime(&now_time_t);
        std::stringstream now_ss;
        now_ss << std::put_time(now_tm, "%Y-%m-%d %H:%M:%S") << "."
                << std::setfill('0') << std::setw(3) << now_ms_remainder;
        std::cout << now_ss.str() << " Received a message with Client/Session ["
		  << std::setfill('0') << std::hex
		  << std::setw(4) << _request->get_client() << "/"
		  << std::setw(4) << _request->get_session() << "]"
		  << std::endl;

        std::shared_ptr<vsomeip::message> its_response
            = vsomeip::runtime::get()->create_response(_request);

        std::shared_ptr<vsomeip::payload> its_payload
            = vsomeip::runtime::get()->create_payload();
        std::vector<vsomeip::byte_t> its_payload_data;
        for (std::size_t i = 0; i < 4; ++i)
            its_payload_data.push_back(vsomeip::byte_t(i % 256));
        its_payload->set_data(its_payload_data);
        its_response->set_payload(its_payload);

        app_->send(its_response);
    }

    void run() {
        std::unique_lock<std::mutex> its_lock(mutex_);
        while (!blocked_)
            condition_.wait(its_lock);
        offer();
    }

private:
    std::shared_ptr<vsomeip::application> app_;
    bool is_registered_;
    bool use_static_routing_;

    std::mutex mutex_;
    std::condition_variable condition_;
    bool blocked_;
    bool running_;

    // blocked_ must be initialized before the thread is started.
    std::thread offer_thread_;
};


    service_sample *its_sample_ptr(nullptr);
    void handle_signal(int _signal) {
        if (its_sample_ptr != nullptr &&
                (_signal == SIGINT || _signal == SIGTERM))
            its_sample_ptr->stop();
    }


int main(int argc, char **argv) {
    bool use_static_routing(false);
    service_sample its_sample(use_static_routing);

    its_sample_ptr = &its_sample;
    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    if (its_sample.init()) {
        its_sample.start();
        return 0;
    } else {
        return 1;
    }
}
