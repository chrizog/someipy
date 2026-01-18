# Copyright (C) 2026 Christian H.
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


from typing import Any, Dict, Tuple
from someipy._internal.session_handler import SessionHandler


class SessionManager:
    """
    Manages SessionHandler instances for each sender-receiver relation.
    Uses a dictionary with (sender, receiver) tuples as keys.
    """

    def __init__(self):
        # Dictionary with keys as (sender, receiver) tuples
        self._sessions: Dict[Tuple[Any, Any], SessionHandler] = {}

    def get_session_handler(
        self, sender: Any, receiver: Any, initial_value: int = 0
    ) -> SessionHandler:
        """
        Get or create a SessionHandler for the given sender-receiver pair.

        Args:
            sender: Identifier for the sender
            receiver: Identifier for the receiver
            initial_value: Initial session ID value (default: 0)

        Returns:
            SessionHandler: The session handler for the given pair
        """
        key = (sender, receiver)

        if key not in self._sessions:
            self._sessions[key] = SessionHandler(initial_value)

        return self._sessions[key]

    def update_session(self, sender: Any, receiver: Any) -> Tuple[int, bool]:
        """
        Update and get the session state for a sender-receiver pair.

        Args:
            sender: Identifier for the sender
            receiver: Identifier for the receiver

        Returns:
            Tuple[int, bool]: Updated session_id and reboot_flag
        """
        session_handler = self.get_session_handler(sender, receiver)
        return session_handler.update_session()

    def get_session_state(self, sender: Any, receiver: Any) -> Tuple[int, bool]:
        """
        Get the current session state without updating it.

        Args:
            sender: Identifier for the sender
            receiver: Identifier for the receiver

        Returns:
            Tuple[int, bool]: Current session_id and reboot_flag

        Raises:
            KeyError: If no session exists for the given pair
        """
        key = (sender, receiver)
        if key not in self._sessions:
            raise KeyError(f"No session found for sender={sender}, receiver={receiver}")

        handler = self._sessions[key]
        return handler.session_id, handler.reboot_flag

    def remove_session(self, sender: Any, receiver: Any) -> bool:
        """
        Remove a session for a sender-receiver pair.

        Args:
            sender: Identifier for the sender
            receiver: Identifier for the receiver

        Returns:
            bool: True if session was removed, False if it didn't exist
        """
        key = (sender, receiver)
        if key in self._sessions:
            del self._sessions[key]
            return True
        return False

    def reset_session(self, sender: Any, receiver: Any, initial_value: int = 0) -> None:
        """
        Reset a session handler for a sender-receiver pair.

        Args:
            sender: Identifier for the sender
            receiver: Identifier for the receiver
            initial_value: New initial value for the session
        """
        key = (sender, receiver)
        self._sessions[key] = SessionHandler(initial_value)

    def get_all_sessions(self) -> Dict[Tuple[Any, Any], SessionHandler]:
        """
        Get all sessions.

        Returns:
            Dict[Tuple[Any, Any], SessionHandler]: Copy of all sessions
        """
        return self._sessions.copy()

    def clear_all_sessions(self) -> None:
        """Remove all sessions."""
        self._sessions.clear()

    def has_session(self, sender: Any, receiver: Any) -> bool:
        """
        Check if a session exists for the given sender-receiver pair.

        Args:
            sender: Identifier for the sender
            receiver: Identifier for the receiver

        Returns:
            bool: True if session exists
        """
        return (sender, receiver) in self._sessions

    def get_session_count(self) -> int:
        """
        Get the total number of active sessions.

        Returns:
            int: Number of sessions
        """
        return len(self._sessions)
