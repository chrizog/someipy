from .someip_sd_header import *


def extract_offered_services(someip_sd_header: SomeIpSdHeader) -> List[SdService]:
    result = []
    service_offers = [
        o for o in someip_sd_header.service_entries if o.sd_entry.type == SdEntryType.OFFER_SERVICE
    ]
    for e in service_offers:
        endpoint = (
            someip_sd_header.options[e.sd_entry.index_first_option].ipv4_address,
            someip_sd_header.options[e.sd_entry.index_first_option].port,
        )
        protocol = someip_sd_header.options[e.sd_entry.index_first_option].protocol
        sd_offered_service = SdService(
            service_id=e.sd_entry.service_id,
            instance_id=e.sd_entry.instance_id,
            major_version=e.sd_entry.major_version,
            minor_version=e.minor_version,
            ttl=e.sd_entry.ttl,
            endpoint=endpoint,
            protocol=protocol,
        )
        result.append(sd_offered_service)
    return result


def extract_subscribe_eventgroup_entries(
    someip_sd_header: SomeIpSdHeader,
) -> List[Tuple[SdEventGroupEntry, SdIPV4EndpointOption]]:
    result = []

    for entry in someip_sd_header.service_entries:
        if entry.sd_entry.type == SdEntryType.SUBSCRIBE_EVENT_GROUP:
            # Check TTL in order to distinguish between subscribe and stop subscribe
            # SUBSCRIBE_EVENT_GROUP = 0x06
            # STOP_SUBSCRIBE_EVENT_GROUP = 0x06 but with TTL set to 0x00
            if entry.sd_entry.ttl != 0x00:
                if entry.sd_entry.num_options_1 > 0:
                    option = someip_sd_header.options[entry.sd_entry.index_first_option]
                    result.append((entry, option))
    return result

def extract_subscribe_ack_eventgroup_entries(
    someip_sd_header: SomeIpSdHeader,
) -> List[SdEventGroupEntry]:
    result = []

    for entry in someip_sd_header.service_entries:
        if entry.sd_entry.type == SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK:
            # Check TTL in order to distinguish between subscribe ack and nack
            # SUBSCRIBE_EVENT_GROUP_ACK = 0x07
            # SUBSCRIBE_EVENT_GROUP_NACK = 0x07  # with TTL set to 0x00
            if entry.sd_entry.ttl != 0x00:
                result.append(entry)
    return result

