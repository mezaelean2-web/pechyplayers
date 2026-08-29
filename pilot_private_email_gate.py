"""Gate temporal y removible para el primer piloto real de Private Email."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PilotPrivateEmailGate:
    reseller_id: int = 6
    purchase_id: int = 41
    account_id: int = 979
    binding_id: int = 1
    provider_config_id: str = "pechy_pilot"

    def allows(self, *, reseller_id, purchase_id, unit, binding):
        return (
            int(reseller_id) == self.reseller_id
            and int(purchase_id) == self.purchase_id
            and isinstance(unit, dict)
            and unit == {
                "type": "cuenta",
                "account_id": self.account_id,
                "profile_id": None,
            }
            and binding.binding_id == self.binding_id
            and binding.inventory_type == "cuenta"
            and binding.account_id == self.account_id
            and binding.profile_id is None
            and binding.provider == "private_email"
            and binding.provider_config_id == self.provider_config_id
            and binding.folder_key == "INBOX"
            and binding.enabled is True
        )
