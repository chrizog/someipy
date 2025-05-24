from typing import Dict, List, Optional
from someipy._internal.someip_endpoint import SomeipEndpoint
from someipy._internal.transport_layer_protocol import TransportLayerProtocol


class SomeipEndpointStorage:
    def __init__(self):
        self._storage: Dict[int, List[SomeipEndpoint]] = {}

    def add_endpoint(self, client_id: int, endpoint: SomeipEndpoint) -> bool:
        """
        Add an endpoint for a client ID.
        Returns True if added successfully, False if client already has 2 endpoints.
        """
        if client_id not in self._storage:
            self._storage[client_id] = [endpoint]
            return True

        if len(self._storage[client_id]) >= 2:
            return False

        self._storage[client_id].append(endpoint)
        return True

    def remove_endpoint(self, client_id: int, endpoint: SomeipEndpoint) -> bool:
        if client_id not in self._storage:
            return False

        try:
            self._storage[client_id].remove(endpoint)
            # Remove client entry if no endpoints left
            if not self._storage[client_id]:
                del self._storage[client_id]
            return True
        except ValueError:
            return False

    def remove_client(self, client_id: int) -> bool:
        if client_id in self._storage:
            del self._storage[client_id]
            return True
        return False

    def get_endpoints(self, client_id: int) -> Optional[List[SomeipEndpoint]]:
        return self._storage.get(client_id, None)

    def get_endpoint(
        self, client_id: int, protocol: TransportLayerProtocol
    ) -> Optional[SomeipEndpoint]:
        endpoints = self._storage.get(client_id, None)
        if endpoints is None:
            return None

        if any(endpoint.protocol() == protocol for endpoint in endpoints):
            # If the client has an endpoint with the same protocol, return all endpoints
            return [
                endpoint for endpoint in endpoints if endpoint.protocol() == protocol
            ][0]
        else:
            return None

    def get_all_endpoints(self) -> List[SomeipEndpoint]:
        """Get all endpoints in the storage"""
        return [
            endpoint for endpoints in self._storage.values() for endpoint in endpoints
        ]

    def has_endpoint(
        self, ip: str, port: int, protocol: TransportLayerProtocol
    ) -> bool:
        """
        Check if an endpoint with the given IP, port, and protocol exists in the storage.
        """
        for endpoints in self._storage.values():
            for endpoint in endpoints:
                if (
                    endpoint.ip == ip
                    and endpoint.port == port
                    and endpoint.protocol() == protocol
                ):
                    return True
        return False

    def __contains__(self, client_id: int) -> bool:
        """Check if a client ID exists in the storage"""
        return client_id in self._storage

    def __len__(self) -> int:
        """Get the number of clients in the storage"""
        return len(self._storage)
