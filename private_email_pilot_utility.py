"""Utilidad administrativa local para un piloto controlado; nunca abre IMAP."""

import argparse
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

import database
import inventory_assignment_access
from mailbox_bindings import AdministrativeMailboxBindingService
from private_email_credentials import ProviderCredentialResolver


PROVIDER="private_email"
CONFIG_ID="pechy_pilot"
FOLDER="INBOX"
RUN_ID_RE=re.compile(r"pp-5b3b-[a-z0-9][a-z0-9-]{5,48}")
REQUIRED={
    "revendedores":{"id","nombre","negocio","correo","password_hash","estado"},
    "reseller_wallets":{"id","revendedor_id","saldo"},
    "revendedores_actividad":{"id","revendedor_id","tipo","descripcion","actor"},
    "nube_clientes":{"id","nombre"},
    "nube_cuentas":{"id","plataforma","correo","cliente_id","nombre_cliente","fecha_entrega",
        "dias_cuenta","fecha_vencimiento","estado","notas","origen","modalidad"},
    "nube_movimientos":{"id","cuenta_id","tipo"},
    "productos":{"id"},
    "reseller_plan_inventory_rules":{"plan_id","plataforma","tipo_unidad","duracion_dias","activo"},
    "reseller_purchases":{"id","revendedor_id","plan_id","cuenta_id","perfil_id","tipo_unidad",
        "operacion_origen","fecha_compra","fecha_activacion","fecha_vencimiento","dias_contratados",
        "precio_pagado","estado_persistido","cortada_at"},
    "reseller_mailbox_bindings":{"id","inventory_type","inventory_account_id","inventory_profile_id",
        "provider","provider_config_id","folder_key","binding_version","enabled"},
}


class PilotUtilityError(Exception):
    def __init__(self,safe_code="pilot_operation_denied"):
        super().__init__(safe_code); self.safe_code=safe_code


def _utcnow(): return datetime.now(timezone.utc)
def _iso(moment): return moment.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def _marker(run_id): return f"MAILBOX_PILOT:{run_id}"


class ControlledMailboxPilotUtility:
    def __init__(self,*,db_path,pilot_run_id,credential_resolver,plan_id,manifest_path=None):
        if not db_path: raise PilotUtilityError("explicit_db_required")
        self.db_path=Path(db_path).expanduser().resolve()
        if not self.db_path.is_file(): raise PilotUtilityError("target_db_invalid")
        self.run_id=str(pilot_run_id or "").strip().lower()
        if not RUN_ID_RE.fullmatch(self.run_id): raise PilotUtilityError("pilot_run_id_invalid")
        if credential_resolver is None: raise PilotUtilityError("provider_config_invalid")
        self.resolver=credential_resolver
        try: self.plan_id=int(plan_id)
        except (TypeError,ValueError): raise PilotUtilityError("plan_invalid") from None
        if self.plan_id<=0: raise PilotUtilityError("plan_invalid")
        self.manifest_path=Path(manifest_path).expanduser().resolve() if manifest_path else None

    def _connect(self,*,readonly=False):
        if readonly:
            conn=sqlite3.connect(self.db_path.as_uri()+"?mode=ro&immutable=1",uri=True)
        else: conn=sqlite3.connect(str(self.db_path))
        conn.row_factory=sqlite3.Row; conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _schema_ok(conn):
        for table,required in REQUIRED.items():
            columns={row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if not required<=columns: return False
        return True

    def _provider_credentials(self):
        try: return self.resolver.resolve(CONFIG_ID)
        except Exception: raise PilotUtilityError("provider_config_invalid") from None

    def _rule(self,conn):
        row=conn.execute("""SELECT r.plan_id,r.plataforma,r.tipo_unidad,r.duracion_dias,r.activo
          FROM reseller_plan_inventory_rules r JOIN productos p ON p.id=r.plan_id
          WHERE r.plan_id=?""",(self.plan_id,)).fetchone()
        if not row or row["activo"]!=1 or row["tipo_unidad"]!="cuenta" or int(row["duracion_dias"] or 0)<=0:
            raise PilotUtilityError("plan_invalid")
        return row

    def _collision(self,conn):
        marker=_marker(self.run_id)
        checks=(
            ("SELECT 1 FROM revendedores WHERE nombre=? OR negocio=? LIMIT 1",(marker,marker)),
            ("SELECT 1 FROM nube_cuentas WHERE origen=? OR notas=? LIMIT 1",(marker,marker)),
        )
        return any(conn.execute(sql,args).fetchone() for sql,args in checks)

    def plan(self):
        creds=self._provider_credentials()
        conn=self._connect(readonly=True)
        try:
            if not self._schema_ok(conn): raise PilotUtilityError("schema_invalid")
            rule=self._rule(conn)
            if self._collision(conn): raise PilotUtilityError("pilot_run_collision")
            return {"ok":True,"operation":"plan","pilot_run_id":self.run_id,
                "provider_config_valid":True,"mailbox_address_resolved":bool(creds.username),
                "plan_id":int(rule["plan_id"]),"unit_type":"cuenta","collision":False,
                "db_explicit":True,"read_only":True}
        finally: conn.close()

    @contextmanager
    def _database_target(self):
        previous=database.DB; database.DB=str(self.db_path)
        try: yield
        finally: database.DB=previous

    def _write_manifest(self,data):
        if self.manifest_path is None: raise PilotUtilityError("manifest_required")
        allowed={"pilot_run_id","reseller_id","wallet_id","activity_id","client_id","account_id",
            "movement_ids","purchase_id","binding_id","binding_version","created_at","updated_at","state"}
        if set(data)-allowed: raise PilotUtilityError("manifest_unsafe")
        self.manifest_path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.manifest_path.with_suffix(self.manifest_path.suffix+".tmp")
        temporary.write_text(json.dumps(data,sort_keys=True,separators=(",",":")),encoding="utf-8")
        os.replace(temporary,self.manifest_path)

    def _load_manifest(self):
        if self.manifest_path is None or not self.manifest_path.is_file():
            raise PilotUtilityError("manifest_required")
        try: data=json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception: raise PilotUtilityError("manifest_invalid") from None
        if data.get("pilot_run_id")!=self.run_id: raise PilotUtilityError("manifest_mismatch")
        return data

    def _create_base(self,creds,now):
        marker=_marker(self.run_id); today=now.date(); conn=self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not self._schema_ok(conn): raise PilotUtilityError("schema_invalid")
            rule=self._rule(conn)
            if self._collision(conn): raise PilotUtilityError("pilot_run_collision")
            reseller_password=secrets.token_urlsafe(32)
            reseller_login=f"{self.run_id}@example.invalid"
            cur=conn.execute("""INSERT INTO revendedores(nombre,negocio,correo,telefono,password_hash,estado)
              VALUES(?,?,?,?,?,'activo')""",(marker,marker,reseller_login,"",generate_password_hash(reseller_password)))
            reseller_id=cur.lastrowid
            cur=conn.execute("INSERT INTO reseller_wallets(revendedor_id,saldo) VALUES(?,0)",(reseller_id,)); wallet_id=cur.lastrowid
            cur=conn.execute("""INSERT INTO revendedores_actividad(revendedor_id,tipo,descripcion,actor)
              VALUES(?,'creacion',?,'mailbox_pilot_utility')""",(reseller_id,marker)); activity_id=cur.lastrowid
            assigned_name=f"Reseller #{reseller_id} - {marker}"[:160]
            cur=conn.execute("INSERT INTO nube_clientes(nombre,telefono,correo,notas,activo) VALUES(?,'','',?,1)",(assigned_name,marker)); client_id=cur.lastrowid
            expiry=today+timedelta(days=int(rule["duracion_dias"]))
            cur=conn.execute("""INSERT INTO nube_cuentas(plataforma,correo,contrasena,pin,tipo_cuenta,
              cliente_id,nombre_cliente,telefono,fecha_entrega,dias_cuenta,fecha_vencimiento,estado,
              notas,origen,modalidad,cantidad_perfiles,duracion_unidad_dias)
              VALUES(?,?,'','','',?,?,'',?,?,?,'activa',?,?,'cuenta_completa',0,?)""",
              (rule["plataforma"],creds.username,client_id,assigned_name,today.isoformat(),
               int(rule["duracion_dias"]),expiry.isoformat(),marker,marker,int(rule["duracion_dias"])))
            account_id=cur.lastrowid
            movements=[]
            for kind,description in (("creacion","Cuenta piloto creada"),("asignacion_cuenta_completa","Cuenta piloto asignada")):
                cur=conn.execute("""INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion,estado_nuevo,cliente_nombre)
                  VALUES(?,?,?,?,?)""",(account_id,kind,description,"activa",assigned_name)); movements.append(cur.lastrowid)
            cur=conn.execute("""INSERT INTO reseller_purchases(revendedor_id,plan_id,cuenta_id,perfil_id,
              tipo_unidad,operacion_origen,fecha_compra,fecha_activacion,fecha_vencimiento,dias_contratados,
              precio_pagado,estado_persistido) VALUES(?,?,?,NULL,'cuenta','purchase',?,?,?,?,0,'active')""",
              (reseller_id,self.plan_id,account_id,today.isoformat(),today.isoformat(),expiry.isoformat(),int(rule["duracion_dias"])))
            purchase_id=cur.lastrowid; conn.commit()
            return {"reseller_id":reseller_id,"wallet_id":wallet_id,"activity_id":activity_id,
                "client_id":client_id,"account_id":account_id,"movement_ids":movements,"purchase_id":purchase_id}
        except Exception:
            conn.rollback(); raise
        finally: conn.close()

    def _delete_base(self,ids):
        conn=self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE"); marker=_marker(self.run_id)
            row=conn.execute("SELECT nombre,negocio FROM revendedores WHERE id=?",(ids["reseller_id"],)).fetchone()
            account=conn.execute("SELECT origen,notas FROM nube_cuentas WHERE id=?",(ids["account_id"],)).fetchone()
            if not row or row["nombre"]!=marker or row["negocio"]!=marker or not account or account["origen"]!=marker:
                raise PilotUtilityError("manifest_mismatch")
            conn.execute("DELETE FROM reseller_purchases WHERE id=?",(ids["purchase_id"],))
            conn.execute("DELETE FROM nube_movimientos WHERE cuenta_id=?",(ids["account_id"],))
            conn.execute("DELETE FROM nube_cuentas WHERE id=?",(ids["account_id"],))
            conn.execute("DELETE FROM nube_clientes WHERE id=?",(ids["client_id"],))
            conn.execute("DELETE FROM revendedores_actividad WHERE revendedor_id=?",(ids["reseller_id"],))
            conn.execute("DELETE FROM reseller_wallets WHERE id=?",(ids["wallet_id"],))
            conn.execute("DELETE FROM revendedores WHERE id=?",(ids["reseller_id"],)); conn.commit()
        except Exception: conn.rollback(); raise
        finally: conn.close()

    def apply(self,*,now=None,fail_after_base=False):
        if self.manifest_path is None: raise PilotUtilityError("manifest_required")
        self.plan(); creds=self._provider_credentials(); now=now or _utcnow()
        ids=self._create_base(creds,now)
        try:
            if fail_after_base: raise PilotUtilityError("injected_failure")
            with self._database_target():
                authorization=inventory_assignment_access.authorize_reseller_message_access(
                    ids["reseller_id"],ids["purchase_id"],now=now.date())
                expected={"type":"cuenta","account_id":ids["account_id"],"profile_id":None}
                if authorization.get("authorized") is not True or authorization.get("inventory_unit")!=expected:
                    raise PilotUtilityError("canonical_authorization_mismatch")
                binding=AdministrativeMailboxBindingService(self.resolver).create_or_replace(
                    reseller_id=ids["reseller_id"],reseller_purchase_id=ids["purchase_id"],
                    provider=PROVIDER,provider_config_id=CONFIG_ID,folder_key=FOLDER,now=now.date())
            manifest={"pilot_run_id":self.run_id,**ids,"binding_id":binding.binding_id,
                "binding_version":binding.binding_version,"created_at":_iso(now),"updated_at":_iso(now),"state":"active"}
            self._write_manifest(manifest); return manifest
        except Exception:
            with self._database_target():
                conn=self._connect()
                try: conn.execute("DELETE FROM reseller_mailbox_bindings WHERE inventory_account_id=?",(ids["account_id"],)); conn.commit()
                finally: conn.close()
            self._delete_base(ids)
            raise

    def teardown(self,*,now=None):
        data=self._load_manifest(); now=now or _utcnow(); conn=self._connect()
        try:
            marker=_marker(self.run_id)
            reseller=conn.execute("SELECT nombre,negocio FROM revendedores WHERE id=?",(data["reseller_id"],)).fetchone()
            account=conn.execute("SELECT origen,notas FROM nube_cuentas WHERE id=?",(data["account_id"],)).fetchone()
            binding=conn.execute("SELECT * FROM reseller_mailbox_bindings WHERE id=?",(data["binding_id"],)).fetchone()
            if not reseller or reseller["nombre"]!=marker or reseller["negocio"]!=marker or not account \
                    or account["origen"]!=marker or not binding or binding["inventory_account_id"]!=data["account_id"]:
                raise PilotUtilityError("manifest_mismatch")
            message_activity=sum(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE reseller_purchase_id=?",
                (data["purchase_id"],)).fetchone()[0] for table in
                ("reseller_mailbox_requests","reseller_authorized_message_deliveries"))
            audit=conn.execute("SELECT COUNT(*) FROM reseller_message_audit_events WHERE reseller_purchase_id=?",
                (data["purchase_id"],)).fetchone()[0]
            unexpected=sum(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE purchase_id=?",
                (data["purchase_id"],)).fetchone()[0] for table in
                ("reseller_purchase_events","reseller_purchase_operations"))
            if unexpected: raise PilotUtilityError("unexpected_dependencies")
        finally: conn.close()
        if message_activity or audit:
            conn=self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE reseller_mailbox_bindings SET enabled=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",(data["binding_id"],))
                conn.execute("UPDATE reseller_purchases SET estado_persistido='cut',cortada_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(data["purchase_id"],))
                conn.execute("UPDATE nube_cuentas SET estado='cortada',fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",(data["account_id"],))
                conn.execute("UPDATE revendedores SET estado='bloqueado',fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",(data["reseller_id"],)); conn.commit()
            except Exception: conn.rollback(); raise
            finally: conn.close()
            data.update(state="retired",updated_at=_iso(now)); self._write_manifest(data); return data
        conn=self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE"); conn.execute("DELETE FROM reseller_mailbox_bindings WHERE id=?",(data["binding_id"],)); conn.commit()
        except Exception: conn.rollback(); raise
        finally: conn.close()
        self._delete_base(data); data.update(state="deleted",updated_at=_iso(now)); self._write_manifest(data); return data


def main(argv=None):
    parser=argparse.ArgumentParser(description="Controlled Private Email mailbox pilot utility")
    parser.add_argument("operation",choices=("plan","apply","teardown")); parser.add_argument("--db",required=True)
    parser.add_argument("--pilot-run-id",required=True); parser.add_argument("--plan-id",required=True,type=int)
    parser.add_argument("--manifest"); args=parser.parse_args(argv)
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"),override=False)
    utility=ControlledMailboxPilotUtility(db_path=args.db,pilot_run_id=args.pilot_run_id,
        credential_resolver=ProviderCredentialResolver(),plan_id=args.plan_id,manifest_path=args.manifest)
    result=getattr(utility,args.operation)(); print(json.dumps(result,sort_keys=True))


if __name__=="__main__": main()
