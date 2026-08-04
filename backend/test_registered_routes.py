from app.main import app

print("=== ALL FASTAPI ROUTES ===")
for route in app.routes:
    if hasattr(route, "endpoint"):
        m_str = ", ".join(sorted(list(getattr(route, "methods", []))))
        print(f"{m_str:12s} {route.path}")

# Check inside router routes
from app.api.endpoints import ondc_bpp
print("\n=== BPP ROUTER SPECIFIC ROUTES ===")
for r in ondc_bpp.router.routes:
    m_str = ", ".join(sorted(list(r.methods)))
    print(f"{m_str:12s} /api/v1/ondc{r.path}")
