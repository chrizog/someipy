from .someip_sd_header import *


def build_offer_service_sd_header(
    service_to_offer: SdService, session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.OFFER_SERVICE,
        0,  # index_first_option
        0,  # index_second_option
        1,  # num_options_1
        0,  # num_options_2
        service_to_offer.service_id,
        service_to_offer.instance_id,
        service_to_offer.major_version,
        service_to_offer.ttl,
    )
    service_entry = SdServiceEntry(
        sd_entry=sd_entry, minor_version=service_to_offer.minor_version
    )

    option_entry_common = SdOptionCommon(
        length=SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE,
        type=SdOptionType.IPV4_ENDPOINT,
        discardable_flag=False,
    )
    sd_option_entry = SdIPV4EndpointOption(
        sd_option_common=option_entry_common,
        ipv4_address=service_to_offer.endpoint[0],
        protocol=service_to_offer.protocol,
        port=service_to_offer.endpoint[1],
    )

    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    # + length of options array (1 option)
    total_length = (
        20
        + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
        + (1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION)
    )
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=(1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION),
        service_entries=[service_entry],
        options=[sd_option_entry],
    )


def build_stop_offer_service_sd_header(
    service_to_offer: SdService, session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.OFFER_SERVICE,
        0,  # index_first_option
        0,  # index_second_option
        1,  # num_options_1
        0,  # num_options_2
        service_to_offer.service_id,
        service_to_offer.instance_id,
        service_to_offer.major_version,
        service_to_offer.ttl,
    )
    service_entry = SdServiceEntry(
        sd_entry=sd_entry, minor_version=service_to_offer.minor_version
    )

    option_entry_common = SdOptionCommon(
        length=SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE,
        type=SdOptionType.IPV4_ENDPOINT,
        discardable_flag=False,
    )
    sd_option_entry = SdIPV4EndpointOption(
        sd_option_common=option_entry_common,
        ipv4_address=service_to_offer.endpoint[0],
        protocol=service_to_offer.protocol,
        port=service_to_offer.endpoint[1],
    )

    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    # + length of options array (1 option)
    total_length = (
        20
        + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
        + (1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION)
    )
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=(1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION),
        service_entries=[service_entry],
        options=[sd_option_entry],
    )


def build_subscribe_eventgroup_ack_entry(
    service_id: int, instance_id: int, major_version: int, ttl: int, event_group_id: int
) -> SdEventGroupEntry:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.SUBSCRIBE_EVENT_GROUP_ACK,
        0,  # index_first_option
        0,  # index_second_option
        0,  # num_options_1
        0,  # num_options_2
        service_id,
        instance_id,
        major_version,
        ttl,
    )

    entry = SdEventGroupEntry(
        sd_entry=sd_entry,
        initial_data_requested_flag=False,
        counter=0,
        eventgroup_id=event_group_id,
    )
    return entry


def build_subscribe_eventgroup_ack_sd_header(
    entry: SdEventGroupEntry, session_id: int, reboot_flag: bool
) -> SomeIpSdHeader:
    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    total_length = 20 + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=0,
        service_entries=[entry],
        options=[],
    )


def build_subscribe_eventgroup_entry(
    service_id: int,
    instance_id: int,
    major_version: int,
    ttl: int,
    event_group_id: int,
    session_id: int,
    reboot_flag: bool,
    endpoint: Tuple[ipaddress.IPv4Address, int],
    protocol: TransportLayerProtocol,
) -> SomeIpSdHeader:
    sd_entry: SdEntry = SdEntry(
        SdEntryType.SUBSCRIBE_EVENT_GROUP,
        0,  # index_first_option
        0,  # index_second_option
        1,  # num_options_1
        0,  # num_options_2
        service_id,
        instance_id,
        major_version,
        ttl,
    )
    entry = SdEventGroupEntry(
        sd_entry=sd_entry,
        initial_data_requested_flag=False,
        counter=0,
        eventgroup_id=event_group_id,
    )

    option_entry_common = SdOptionCommon(
        length=SD_IPV4ENDPOINT_OPTION_LENGTH_VALUE,
        type=SdOptionType.IPV4_ENDPOINT,
        discardable_flag=False,
    )
    sd_option_entry = SdIPV4EndpointOption(
        sd_option_common=option_entry_common,
        ipv4_address=endpoint[0],
        protocol=protocol,
        port=endpoint[1],
    )

    # 20 bytes for header and length values of entries and options
    # + length of entries array (1 entry)
    # + length of options array (1 option)
    total_length = (
        20
        + (1 * SD_SINGLE_ENTRY_LENGTH_BYTES)
        + (1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION)
    )
    someip_header = SomeIpHeader.generate_sd_header(
        length=total_length, session_id=session_id
    )

    return SomeIpSdHeader(
        someip_header=someip_header,
        reboot_flag=reboot_flag,
        unicast_flag=True,
        length_entries=(1 * SD_SINGLE_ENTRY_LENGTH_BYTES),
        length_options=(1 * SD_BYTE_LENGTH_IP4ENDPOINT_OPTION),
        service_entries=[entry],
        options=[sd_option_entry],
    )
