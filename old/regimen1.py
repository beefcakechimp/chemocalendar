#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any


# ---------------------------
# Data models
# ---------------------------
@dataclass
class Chemotherapy:
    name: str
    route: str
    dose: str
    frequency: str
    duration: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Chemotherapy":
        return Chemotherapy(
            name=d.get("name", "").strip(),
            route=d.get("route", "").strip(),
            dose=str(d.get("dose", "")).strip(),
            frequency=d.get("frequency", "").strip(),
            duration=d.get("duration", "").strip(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Regimen:
    name: str  # required, used as unique key in the JSON store
    disease_state: Optional[str] = None
    chemotherapy: List[Chemotherapy] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Regimen":
        return Regimen(
            name=d["name"].strip(),
            disease_state=(d.get("disease_state") or None),
            chemotherapy=[Chemotherapy.from_dict(c) for c in d.get("chemotherapy", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "disease_state": self.disease_state,
            "chemotherapy": [c.to_dict() for c in self.chemotherapy],
        }


# ---------------------------
# Storage (atomic JSON)
# ---------------------------
class RegimenBank:
    def __init__(self, path: str = "regimenbank.json") -> None:
        self.path = path
        self._db: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self.load()

    def load(self) -> None:
        if os.path.exists(self.path) and os.path.getsize(self.path) > 0:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("regimenbank.json is malformed (expected an object).")
                self._db = data
        else:
            self._db = {}
        self._loaded = True

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=os.path.dirname(self.path) or ".") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, self.path)

    def save(self) -> None:
        self._atomic_write(self._db)

    # -----------------------
    # CRUD
    # -----------------------
    def add_regimen(self, regimen: Regimen, overwrite: bool = False) -> None:
        key = regimen.name.strip()
        if not key:
            raise ValueError("Regimen name is required.")
        if key in self._db and not overwrite:
            raise KeyError(f"Regimen '{key}' already exists. Use overwrite=True or update.")
        self._db[key] = regimen.to_dict()
        self.save()

    def get_regimen(self, name: str) -> Optional[Regimen]:
        rec = self._db.get(name.strip())
        return Regimen.from_dict(rec) if rec else None

    def list_regimens(self) -> List[str]:
        return sorted(self._db.keys())

    def delete_regimen(self, name: str) -> bool:
        key = name.strip()
        if key in self._db:
            del self._db[key]
            self.save()
            return True
        return False

    def update_regimen(
        self,
        name: str,
        *,
        disease_state: Optional[Optional[str]] = None,
        chemotherapy: Optional[List[Chemotherapy]] = None,
        append_chemo: Optional[List[Chemotherapy]] = None,
    ) -> None:
        """Update a regimen by name.

        Args:
            name: Regimen key.
            disease_state: If provided, sets disease_state (use None to clear).
            chemotherapy: If provided, replaces entire chemotherapy list.
            append_chemo: If provided, appends to chemotherapy list.
        """
        key = name.strip()
        if key not in self._db:
            raise KeyError(f"Regimen '{key}' not found.")
        rec = Regimen.from_dict(self._db[key])

        if disease_state is not None:
            rec.disease_state = disease_state or None
        if chemotherapy is not None:
            rec.chemotherapy = chemotherapy
        if append_chemo:
            rec.chemotherapy.extend(append_chemo)

        self._db[key] = rec.to_dict()
        self.save()

    # Convenience: update a single chemotherapy by index.
    def update_chemotherapy_at(
        self,
        name: str,
        index: int,
        *,
        chemo_updates: Dict[str, str],
    ) -> None:
        key = name.strip()
        if key not in self._db:
            raise KeyError(f"Regimen '{key}' not found.")
        rec = Regimen.from_dict(self._db[key])
        if not (0 <= index < len(rec.chemotherapy)):
            raise IndexError("Chemotherapy index out of range.")
        chemo = rec.chemotherapy[index]
        for field_name, value in chemo_updates.items():
            if hasattr(chemo, field_name):
                setattr(chemo, field_name, str(value).strip())
        rec.chemotherapy[index] = chemo
        self._db[key] = rec.to_dict()
        self.save()


# ---------------------------
# Interactive helpers (optional)
# ---------------------------
def _prompt_nonempty(prompt: str, default: Optional[str] = None) -> str:
    while True:
        s = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        if s:
            return s
        if default is not None:
            return default

def prompt_chemotherapy(existing: Optional[Chemotherapy] = None) -> Chemotherapy:
    """Prompt the user for any missing chemotherapy fields (or all, if desired)."""
    existing = existing or Chemotherapy("", "", "", "", "")
    name = _prompt_nonempty("Chemotherapy name", existing.name or None)
    route = _prompt_nonempty("Route", existing.route or None)
    dose = _prompt_nonempty("Dose (e.g., '75 mg/m^2')", existing.dose or None)
    frequency = _prompt_nonempty("Frequency (e.g., 'Days 1-7, q28d')", existing.frequency or None)
    duration = _prompt_nonempty("Duration (e.g., '7 days')", existing.duration or None)
    return Chemotherapy(name=name, route=route, dose=dose, frequency=frequency, duration=duration)


# ---------------------------
# Minimal CLI (optional)
# ---------------------------
def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="Manage chemotherapy regimens in regimenbank.json")
    parser.add_argument("--db", default="regimenbank.json", help="Path to JSON file (default: regimenbank.json)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a regimen")
    p_add.add_argument("--name", required=True, help="Regimen name (unique key)")
    p_add.add_argument("--disease", default=None, help="Disease state (optional)")
    p_add.add_argument(
        "--chemo",
        action="append",
        metavar="ITEM",
        help="Chemotherapy item as 'name;route;dose;frequency;duration' (repeatable). "
             "If omitted, you will be prompted to enter one or more."
    )
    p_add.add_argument("--overwrite", action="store_true", help="Overwrite if regimen exists")

    # get
    p_get = sub.add_parser("get", help="Get a regimen by name")
    p_get.add_argument("--name", required=True)

    # list
    sub.add_parser("list", help="List regimen names")

    # delete
    p_del = sub.add_parser("delete", help="Delete a regimen")
    p_del.add_argument("--name", required=True)

    # update
    p_upd = sub.add_parser("update", help="Update regimen fields")
    p_upd.add_argument("--name", required=True)
    p_upd.add_argument("--disease", help="Set/replace disease_state (use empty string to clear)")
    p_upd.add_argument(
        "--chemo",
        action="append",
        metavar="ITEM",
        help="Replace entire chemotherapy list with one or more items formatted as "
             "'name;route;dose;frequency;duration' (repeatable)."
    )
    p_upd.add_argument(
        "--append-chemo",
        action="append",
        metavar="ITEM",
        help="Append chemotherapy item(s) formatted as 'name;route;dose;frequency;duration' (repeatable)."
    )

    # update-chemo-at
    p_upd_idx = sub.add_parser("update-chemo-at", help="Update a single chemotherapy entry by index")
    p_upd_idx.add_argument("--name", required=True)
    p_upd_idx.add_argument("--index", type=int, required=True)
    p_upd_idx.add_argument("--set-name")
    p_upd_idx.add_argument("--set-route")
    p_upd_idx.add_argument("--set-dose")
    p_upd_idx.add_argument("--set-frequency")
    p_upd_idx.add_argument("--set-duration")

    args = parser.parse_args()
    bank = RegimenBank(args.db)

    def parse_items(items: Optional[List[str]]) -> Optional[List[Chemotherapy]]:
        if not items:
            return None
        out: List[Chemotherapy] = []
        for item in items:
            parts = [p.strip() for p in item.split(";")]
            if len(parts) != 5:
                raise ValueError("Each --chemo/--append-chemo must have 5 semicolon-separated fields: "
                                 "name;route;dose;frequency;duration")
            out.append(Chemotherapy(*parts))
        return out

    if args.cmd == "add":
        chemos = parse_items(args.chemo)
        if not chemos:
            # interactive: at least one chemo; user can add multiple
            chemos = []
            print("No chemotherapy items provided. Enter at least one.")
            while True:
                chemos.append(prompt_chemotherapy())
                more = input("Add another chemotherapy item? [y/N]: ").strip().lower()
                if more not in ("y", "yes"):
                    break
        regimen = Regimen(name=args.name, disease_state=(args.disease or None), chemotherapy=chemos)
        bank.add_regimen(regimen, overwrite=args.overwrite)
        print(f"Saved regimen '{args.name}'.")

    elif args.cmd == "get":
        reg = bank.get_regimen(args.name)
        if not reg:
            print("Not found.")
        else:
            print(json.dumps(reg.to_dict(), indent=2, ensure_ascii=False))

    elif args.cmd == "list":
        for k in bank.list_regimens():
            print(k)

    elif args.cmd == "delete":
        ok = bank.delete_regimen(args.name)
        print("Deleted." if ok else "Not found.")

    elif args.cmd == "update":
        replace = parse_items(args.chemo)
        append = parse_items(args.append_chemo)
        bank.update_regimen(
            args.name,
            disease_state=(args.disease if args.disease is not None else None),
            chemotherapy=replace,
            append_chemo=append,
        )
        print(f"Updated regimen '{args.name}'.")

    elif args.cmd == "update-chemo-at":
        updates = {}
        if args.set_name is not None: updates["name"] = args.set_name
        if args.set_route is not None: updates["route"] = args.set_route
        if args.set_dose is not None: updates["dose"] = args.set_dose
        if args.set_frequency is not None: updates["frequency"] = args.set_frequency
        if args.set_duration is not None: updates["duration"] = args.set_duration
        if not updates:
            raise SystemExit("No updates provided.")
        bank.update_chemotherapy_at(args.name, args.index, chemo_updates=updates)
        print(f"Updated chemotherapy index {args.index} in '{args.name}'.")


if __name__ == "__main__":
    _cli()
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any


# ---------------------------
# Data models
# ---------------------------
@dataclass
class Chemotherapy:
    name: str
    route: str
    dose: str
    frequency: str
    duration: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Chemotherapy":
        return Chemotherapy(
            name=d.get("name", "").strip(),
            route=d.get("route", "").strip(),
            dose=str(d.get("dose", "")).strip(),
            frequency=d.get("frequency", "").strip(),
            duration=d.get("duration", "").strip(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Regimen:
    name: str  # required, used as unique key in the JSON store
    disease_state: Optional[str] = None
    chemotherapy: List[Chemotherapy] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Regimen":
        return Regimen(
            name=d["name"].strip(),
            disease_state=(d.get("disease_state") or None),
            chemotherapy=[Chemotherapy.from_dict(c) for c in d.get("chemotherapy", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "disease_state": self.disease_state,
            "chemotherapy": [c.to_dict() for c in self.chemotherapy],
        }


# ---------------------------
# Storage (atomic JSON)
# ---------------------------
class RegimenBank:
    def __init__(self, path: str = "regimenbank.json") -> None:
        self.path = path
        self._db: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self.load()

    def load(self) -> None:
        if os.path.exists(self.path) and os.path.getsize(self.path) > 0:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("regimenbank.json is malformed (expected an object).")
                self._db = data
        else:
            self._db = {}
        self._loaded = True

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=os.path.dirname(self.path) or ".") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, self.path)

    def save(self) -> None:
        self._atomic_write(self._db)

    # -----------------------
    # CRUD
    # -----------------------
    def add_regimen(self, regimen: Regimen, overwrite: bool = False) -> None:
        key = regimen.name.strip()
        if not key:
            raise ValueError("Regimen name is required.")
        if key in self._db and not overwrite:
            raise KeyError(f"Regimen '{key}' already exists. Use overwrite=True or update.")
        self._db[key] = regimen.to_dict()
        self.save()

    def get_regimen(self, name: str) -> Optional[Regimen]:
        rec = self._db.get(name.strip())
        return Regimen.from_dict(rec) if rec else None

    def list_regimens(self) -> List[str]:
        return sorted(self._db.keys())

    def delete_regimen(self, name: str) -> bool:
        key = name.strip()
        if key in self._db:
            del self._db[key]
            self.save()
            return True
        return False

    def update_regimen(
        self,
        name: str,
        *,
        disease_state: Optional[Optional[str]] = None,
        chemotherapy: Optional[List[Chemotherapy]] = None,
        append_chemo: Optional[List[Chemotherapy]] = None,
    ) -> None:
        """Update a regimen by name.

        Args:
            name: Regimen key.
            disease_state: If provided, sets disease_state (use None to clear).
            chemotherapy: If provided, replaces entire chemotherapy list.
            append_chemo: If provided, appends to chemotherapy list.
        """
        key = name.strip()
        if key not in self._db:
            raise KeyError(f"Regimen '{key}' not found.")
        rec = Regimen.from_dict(self._db[key])

        if disease_state is not None:
            rec.disease_state = disease_state or None
        if chemotherapy is not None:
            rec.chemotherapy = chemotherapy
        if append_chemo:
            rec.chemotherapy.extend(append_chemo)

        self._db[key] = rec.to_dict()
        self.save()

    # Convenience: update a single chemotherapy by index.
    def update_chemotherapy_at(
        self,
        name: str,
        index: int,
        *,
        chemo_updates: Dict[str, str],
    ) -> None:
        key = name.strip()
        if key not in self._db:
            raise KeyError(f"Regimen '{key}' not found.")
        rec = Regimen.from_dict(self._db[key])
        if not (0 <= index < len(rec.chemotherapy)):
            raise IndexError("Chemotherapy index out of range.")
        chemo = rec.chemotherapy[index]
        for field_name, value in chemo_updates.items():
            if hasattr(chemo, field_name):
                setattr(chemo, field_name, str(value).strip())
        rec.chemotherapy[index] = chemo
        self._db[key] = rec.to_dict()
        self.save()


# ---------------------------
# Interactive helpers (optional)
# ---------------------------
def _prompt_nonempty(prompt: str, default: Optional[str] = None) -> str:
    while True:
        s = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        if s:
            return s
        if default is not None:
            return default

def prompt_chemotherapy(existing: Optional[Chemotherapy] = None) -> Chemotherapy:
    """Prompt the user for any missing chemotherapy fields (or all, if desired)."""
    existing = existing or Chemotherapy("", "", "", "", "")
    name = _prompt_nonempty("Chemotherapy name", existing.name or None)
    route = _prompt_nonempty("Route", existing.route or None)
    dose = _prompt_nonempty("Dose (e.g., '75 mg/m^2')", existing.dose or None)
    frequency = _prompt_nonempty("Frequency (e.g., 'Days 1-7, q28d')", existing.frequency or None)
    duration = _prompt_nonempty("Duration (e.g., '7 days')", existing.duration or None)
    return Chemotherapy(name=name, route=route, dose=dose, frequency=frequency, duration=duration)


# ---------------------------
# Minimal CLI (optional)
# ---------------------------
def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="Manage chemotherapy regimens in regimenbank.json")
    parser.add_argument("--db", default="regimenbank.json", help="Path to JSON file (default: regimenbank.json)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a regimen")
    p_add.add_argument("--name", required=True, help="Regimen name (unique key)")
    p_add.add_argument("--disease", default=None, help="Disease state (optional)")
    p_add.add_argument(
        "--chemo",
        action="append",
        metavar="ITEM",
        help="Chemotherapy item as 'name;route;dose;frequency;duration' (repeatable). "
             "If omitted, you will be prompted to enter one or more."
    )
    p_add.add_argument("--overwrite", action="store_true", help="Overwrite if regimen exists")

    # get
    p_get = sub.add_parser("get", help="Get a regimen by name")
    p_get.add_argument("--name", required=True)

    # list
    sub.add_parser("list", help="List regimen names")

    # delete
    p_del = sub.add_parser("delete", help="Delete a regimen")
    p_del.add_argument("--name", required=True)

    # update
    p_upd = sub.add_parser("update", help="Update regimen fields")
    p_upd.add_argument("--name", required=True)
    p_upd.add_argument("--disease", help="Set/replace disease_state (use empty string to clear)")
    p_upd.add_argument(
        "--chemo",
        action="append",
        metavar="ITEM",
        help="Replace entire chemotherapy list with one or more items formatted as "
             "'name;route;dose;frequency;duration' (repeatable)."
    )
    p_upd.add_argument(
        "--append-chemo",
        action="append",
        metavar="ITEM",
        help="Append chemotherapy item(s) formatted as 'name;route;dose;frequency;duration' (repeatable)."
    )

    # update-chemo-at
    p_upd_idx = sub.add_parser("update-chemo-at", help="Update a single chemotherapy entry by index")
    p_upd_idx.add_argument("--name", required=True)
    p_upd_idx.add_argument("--index", type=int, required=True)
    p_upd_idx.add_argument("--set-name")
    p_upd_idx.add_argument("--set-route")
    p_upd_idx.add_argument("--set-dose")
    p_upd_idx.add_argument("--set-frequency")
    p_upd_idx.add_argument("--set-duration")

    args = parser.parse_args()
    bank = RegimenBank(args.db)

    def parse_items(items: Optional[List[str]]) -> Optional[List[Chemotherapy]]:
        if not items:
            return None
        out: List[Chemotherapy] = []
        for item in items:
            parts = [p.strip() for p in item.split(";")]
            if len(parts) != 5:
                raise ValueError("Each --chemo/--append-chemo must have 5 semicolon-separated fields: "
                                 "name;route;dose;frequency;duration")
            out.append(Chemotherapy(*parts))
        return out

    if args.cmd == "add":
        chemos = parse_items(args.chemo)
        if not chemos:
            # interactive: at least one chemo; user can add multiple
            chemos = []
            print("No chemotherapy items provided. Enter at least one.")
            while True:
                chemos.append(prompt_chemotherapy())
                more = input("Add another chemotherapy item? [y/N]: ").strip().lower()
                if more not in ("y", "yes"):
                    break
        regimen = Regimen(name=args.name, disease_state=(args.disease or None), chemotherapy=chemos)
        bank.add_regimen(regimen, overwrite=args.overwrite)
        print(f"Saved regimen '{args.name}'.")

    elif args.cmd == "get":
        reg = bank.get_regimen(args.name)
        if not reg:
            print("Not found.")
        else:
            print(json.dumps(reg.to_dict(), indent=2, ensure_ascii=False))

    elif args.cmd == "list":
        for k in bank.list_regimens():
            print(k)

    elif args.cmd == "delete":
        ok = bank.delete_regimen(args.name)
        print("Deleted." if ok else "Not found.")

    elif args.cmd == "update":
        replace = parse_items(args.chemo)
        append = parse_items(args.append_chemo)
        bank.update_regimen(
            args.name,
            disease_state=(args.disease if args.disease is not None else None),
            chemotherapy=replace,
            append_chemo=append,
        )
        print(f"Updated regimen '{args.name}'.")

    elif args.cmd == "update-chemo-at":
        updates = {}
        if args.set_name is not None: updates["name"] = args.set_name
        if args.set_route is not None: updates["route"] = args.set_route
        if args.set_dose is not None: updates["dose"] = args.set_dose
        if args.set_frequency is not None: updates["frequency"] = args.set_frequency
        if args.set_duration is not None: updates["duration"] = args.set_duration
        if not updates:
            raise SystemExit("No updates provided.")
        bank.update_chemotherapy_at(args.name, args.index, chemo_updates=updates)
        print(f"Updated chemotherapy index {args.index} in '{args.name}'.")


if __name__ == "__main__":
    _cli()
