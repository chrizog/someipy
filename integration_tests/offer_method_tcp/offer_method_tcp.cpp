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

class client_sample
{
public:
    client_sample(bool _use_tcp, uint32_t _cycle)
        : app_(vsomeip::runtime::get()->create_application("Hello")),
          request_(vsomeip::runtime::get()->create_request(_use_tcp)),
          use_tcp_(_use_tcp),
          cycle_(_cycle),
          is_available_(false),
          sender_(std::bind(&client_sample::run, this))
    {
    }

    bool init()
    {
        if (!app_->init())
        {
            std::cerr << "Couldn't initialize application" << std::endl;
            return false;
        }

        std::cout << "Client settings [protocol="
                  << (use_tcp_ ? "TCP" : "UDP")
                  << ":cycle="
                  << cycle_
                  << "]"
                  << std::endl;

        app_->register_state_handler(
            std::bind(
                &client_sample::on_state,
                this,
                std::placeholders::_1));

        app_->register_message_handler(
            vsomeip::ANY_SERVICE, SAMPLE_INSTANCE_ID, vsomeip::ANY_METHOD,
            std::bind(&client_sample::on_message,
                      this,
                      std::placeholders::_1));

        request_->set_service(SAMPLE_SERVICE_ID);
        request_->set_instance(SAMPLE_INSTANCE_ID);
        request_->set_method(SAMPLE_METHOD_ID);
        request_->set_interface_version(1);

        std::shared_ptr<vsomeip::payload> its_payload = vsomeip::runtime::get()->create_payload();
        std::vector<vsomeip::byte_t> its_payload_data;
        for (std::size_t i = 0; i < 10; ++i)
            its_payload_data.push_back(vsomeip::byte_t(i % 256));
        its_payload->set_data(its_payload_data);
        request_->set_payload(its_payload);

        app_->register_availability_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID,
                                            std::bind(&client_sample::on_availability,
                                                      this,
                                                      std::placeholders::_1, std::placeholders::_2, std::placeholders::_3));

        app_->register_availability_handler(SAMPLE_SERVICE_ID + 1, SAMPLE_INSTANCE_ID,
                                            std::bind(&client_sample::on_availability,
                                                      this,
                                                      std::placeholders::_1, std::placeholders::_2, std::placeholders::_3));
        return true;
    }

    void start()
    {
        app_->start();
    }

    void on_state(vsomeip::state_type_e _state)
    {
        if (_state == vsomeip::state_type_e::ST_REGISTERED)
        {
            app_->request_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
        }
    }

    void on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available)
    {
        std::cout << "Service ["
                  << std::setw(4) << std::setfill('0') << std::hex << _service << "." << _instance
                  << "] is "
                  << (_is_available ? "available." : "NOT available.")
                  << std::endl;

        if (SAMPLE_SERVICE_ID == _service && SAMPLE_INSTANCE_ID == _instance)
        {
            std::lock_guard<std::mutex> its_lock(mutex_);

            if (is_available_ && !_is_available)
            {
                is_available_ = false;
            }
            else if (_is_available && !is_available_)
            {
                is_available_ = true;
            }
        }
    }

    void on_message(const std::shared_ptr<vsomeip::message> &_response)
    {
        std::cout << "Received a response from Service ["
                  << std::setfill('0') << std::hex
                  << std::setw(4) << _response->get_service()
                  << "."
                  << std::setw(4) << _response->get_instance()
                  << "] to Client/Session ["
                  << std::setw(4) << _response->get_client()
                  << "/"
                  << std::setw(4) << _response->get_session()
                  << "]"
                  << std::endl;
    }

    void run()
    {
        while (true)
        {
            bool send_data = false;
            {
                std::lock_guard<std::mutex> its_lock(mutex_);
                if (is_available_)
                {
                    send_data = true;
                }
            }

            if (send_data)
            {
                app_->send(request_);
                std::cout << "Client/Session ["
                          << std::setfill('0') << std::hex
                          << std::setw(4) << request_->get_client()
                          << "/"
                          << std::setw(4) << request_->get_session()
                          << "] sent a request to Service ["
                          << std::setw(4) << request_->get_service()
                          << "."
                          << std::setw(4) << request_->get_instance()
                          << "]"
                          << std::endl;
            }

            std::cout << "sleep for " << std::to_string(cycle_) << " ms" << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(cycle_));
        }
    }

private:
    std::shared_ptr<vsomeip::application> app_;
    std::shared_ptr<vsomeip::message> request_;
    bool use_tcp_;
    uint32_t cycle_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool running_;
    bool is_available_;

    std::thread sender_;
};

client_sample *its_sample_ptr(nullptr);

int main(int argc, char **argv)
{
    bool use_tcp = true;
    uint32_t cycle = 1000; // Default: 1s

    std::string tcp_enable("--tcp");
    std::string udp_enable("--udp");
    std::string cycle_arg("--cycle");

    int i = 1;
    while (i < argc)
    {
        if (tcp_enable == argv[i])
        {
            use_tcp = true;
        }
        else if (udp_enable == argv[i])
        {
            use_tcp = false;
        }
        else if (cycle_arg == argv[i] && i + 1 < argc)
        {
            i++;
            std::stringstream converter;
            converter << argv[i];
            converter >> cycle;
        }
        i++;
    }

    client_sample its_sample(use_tcp, cycle);
    its_sample_ptr = &its_sample;

    if (its_sample.init())
    {
        its_sample.start();
        return 0;
    }
    else
    {
        return 1;
    }
}
