from __future__ import annotations


def create_app():
    try:
        from fastapi import FastAPI
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("FastAPI chưa được cài trong môi trường hiện tại") from exc

    app = FastAPI(title="VideoTransDub")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
