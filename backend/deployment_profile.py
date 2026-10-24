"""Explicit execution scope; a container view never becomes host hardware data."""

from dataclasses import dataclass
import ipaddress


@dataclass(frozen=True)
class Profile:
    kind: str = 'native'
    trusted_bridge_peers: tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in ('native', 'container'):
            raise ValueError('Unknown runtime profile.')
        if self.kind == 'native' and self.trusted_bridge_peers:
            raise ValueError('Native mode cannot trust bridge peers.')
        if len(self.trusted_bridge_peers) > 5:
            raise ValueError('Too many trusted bridge peers.')
        for value in self.trusted_bridge_peers:
            address = ipaddress.ip_address(value)
            if (
                not address.is_private
                or address.is_unspecified
                or address.is_multicast
                or address.is_link_local
            ):
                raise ValueError('Bridge peers must be explicit private addresses.')

    def trusts(self, peer):
        try:
            address = ipaddress.ip_address(peer)
            return any(
                address == ipaddress.ip_address(value) for value in self.trusted_bridge_peers
            )
        except ValueError:
            return False
