# C07 notification compatibility design

The design is now implemented for the supported APP-BE-014 producer scope. Current
behavior, preserved legacy shapes, migration/retention, actual EMAIL gateway channel,
missing later producers and receipt limits are frozen in
[unified-notifications-handoff.md](unified-notifications-handoff.md). The code-owned map
is synchronized with notification-map.json; its fixtures validate the whole planned
map, while actual integration evidence covers implemented producer hooks.

The original direct-SMTP proposal was reconciled against the real provider: this
repository implements EMAIL through an allowlisted HTTPS gateway. The actual owned
worker test verifies that transport and its receipt, not downstream SMTP. Calendar,
reminder, incident and recovery producers remain in their explicit later owners.
