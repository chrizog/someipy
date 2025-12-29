# Copyright (C) 2025 Christian H.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from typing import Dict, List, Tuple

from someipy._internal._daemon.subscription import Subscription


class SubscriptionStorage:

    def __init__(self):
        self._subscriptions_by_client: Dict[int, List[Subscription]] = {}

    def add_subscription(self, client_id: int, subscription: Subscription):
        if client_id not in self._subscriptions_by_client:
            self._subscriptions_by_client[client_id] = []
            self._subscriptions_by_client[client_id].append(subscription)
        else:
            if subscription not in self._subscriptions_by_client[client_id]:
                self._subscriptions_by_client[client_id].append(subscription)

    def remove_subscription(self, client_id: int, subscription: Subscription):
        if client_id in self._subscriptions_by_client:
            if subscription in self._subscriptions_by_client[client_id]:
                self._subscriptions_by_client[client_id].remove(subscription)

                if len(self._subscriptions_by_client[client_id]) == 0:
                    del self._subscriptions_by_client[client_id]

    @property
    def subscriptions(self) -> List[Subscription]:
        """
        Get all subscriptions from all clients.
        """
        subscriptions = []
        for client_subscriptions in self._subscriptions_by_client.values():
            subscriptions.extend(client_subscriptions)
        return subscriptions

    def __len__(self) -> int:
        """
        Get the total number of subscriptions across all clients.
        """
        total = 0
        for client_subscriptions in self._subscriptions_by_client.values():
            total += len(client_subscriptions)
        return total

    def get_client_ids(self, subscription: Subscription) -> List[int]:
        """
        Get all client ids (writer ids) that have the given subscription.
        """
        client_ids = []
        for client_id, subscriptions in self._subscriptions_by_client.items():
            if subscription in subscriptions:
                client_ids.append(client_id)
        return client_ids

    def has_subscriptions(
        self,
        service_id: int,
        instance_id: int,
        major_version: int,
    ) -> List[Tuple[Subscription, int]]:
        """
        Check if there are any subscriptions for the given service id, instance id, major version and protocol.
        Returns a list of tuples containing the subscription and the writer id (UDS client).
        """
        subscriptions_to_return = []
        for writer_id, subscriptions in self._subscriptions_by_client.items():
            for subscription in subscriptions:
                if (
                    subscription.service_id == service_id
                    and subscription.instance_id == instance_id
                    and subscription.major_version == major_version
                ):
                    subscriptions_to_return.append((subscription, writer_id))

        return subscriptions_to_return

    def remove_client(self, client_id: int):
        if client_id in self._subscriptions_by_client:
            del self._subscriptions_by_client[client_id]
