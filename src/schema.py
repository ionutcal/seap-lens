"""Maps every column name used in the SEAP files to one schema per kind of file."""

import re
from typing import Optional

import pandas as pd

CONTRACT_ALIASES = {
    "authority_name": ["AutoritateContractanta", "AUTORITATE_CONTRACTANTA", "Autoritate contractanta", "DENUMIRE_AC"],
    "authority_cui": ["AutoritateContractantaCUI", "AUTORITATE_CONTRACTANTA_CUI", "CUI autoritate conractanta",
                      "CUI autoritate contractanta", "CUI_AC", "CUI"],
    "authority_type": ["TipAC", "TIP_AUTORITATE", "Tip autoritate contractanta", "Tip autoritate"],
    "authority_activity": ["TipActivitateAC", "TIP__ACTIVITATE_AUTORITATE", "Tip activitate autoritate contractanta",
                           "Tip activitate"],
    "authority_nuts": ["COD_NUTS"],
    "notice_type": ["Tip", "TIP_ANUNT", "Tip anunt"],
    "contract_type": ["TipContract", "TIP_CONTRACT", "Tip contract"],
    "procedure_type": ["TipProcedura", "TIP_PROCEDURA", "Tip procedura"],
    "agreement_type": ["TipIncheiereContract", "TIP_INCHEIERE_CONTRACT", "Tip incheiere contract",
                       "Tip inchiere contract"],
    "concluded_through": ["INCHEIAT_PRIN", "Incheiar prin", "Incheiat prin"],
    "criterion": ["TipCriteriiAtribuire", "TIP_CRITERII_ATRIBUIRE", "Tip criteriu de atribuire",
                  "Tip criterii de atribuire", "Criterii de atribuire"],
    "e_auction": ["CuLicitatieElectronica", "CU_LICITATIE_ELECTRONICA", "Cu licitatie electronica?",
                  "Licitatie electronica?"],
    "award_notice_id": ["NumarAnuntAtribuire", "NUMAR_ANUNT_ATRIBUIRE", "Numar anunt atribuire"],
    "award_notice_date": ["DataAnuntAtribuire", "DATA_ANUNT_ATRIBUIRE", "Data anunt atribuire",
                          "Data publicare anunt atribuire", "Data publicare.1"],
    "participation_notice_id": ["NumarAnuntParticipare", "NUMAR_ANUNT_PARTICIPARE", "Numar anunt participare",
                                "NUMAR_ANUNT_AI", "NUMAR_ANUNT_INITIERE", "Numar anunt initiere"],
    "participation_notice_date": ["DataAnuntParticipare", "DATA_ANUNT_PARTICIPARE", "Data anunt participare",
                                  "DATA_PUBLICARE_AI", "DATA_ANUNT_INITIERE", "Data anunt initiere",
                                  "Data publicare anunt initiere", "Data publicare"],
    "lot_number": ["NUMAR_LOT", "Numar lot"],
    "contract_number": ["NumarContract", "NUMAR_CONTRACT", "Numar contract"],
    "contract_date": ["DataContract", "DATA_CONTRACT", "Data contract", "Data publicare contract"],
    "contract_title": ["TitluContract", "TITLU_CONTRACT", "Denumire contract", "DENUMIRE_CONTRACT"],
    "bid_count": ["NumarOfertePrimite", "NUMAR_OFERTE", "Numar oferte"],
    "value_ron": ["ValoareRON", "VALOARE_CONTRACT_RON", "Valoare contract (RON)", "Valoare atribuita (RON)"],
    "estimated_value": ["ValoareEstimataParticipare", "VALOARE_ESTIMATA_PARTICIPARE", "Valoare estimata",
                        "VALOARE_ESTIMATA_RON"],
    "estimated_currency": ["MonedaValoareEstimataParticipare", "MONEDA_VALOARE_ESTIMATA", "Moneda"],
    "cpv_code": ["CPVCode", "CPV_CODE", "Cod CPV"],
    "cpv_name": ["DENUMIRE_CPV", "Denumire CPV"],
    "winner_name": ["Castigator", "CASTIGATOR", "Catigator", "OFERTANT", "Ofertant", "Ofertant castigator"],
    "winner_cui": ["CastigatorCUI", "CASTIGATOR_CUI", "CUI castigator", "CUI_OF", "CUI_OFERTANT", "CUI ofertant",
                   "CUI ofertant castigator"],
    "winner_country": ["CastigatorTara", "CASTIGATOR_TARA", "Tara castigator", "TARA_CASTIGATOR", "Tara ofertant",
                       "Tara"],
    "winner_city": ["CastigatorLocalitate", "CASTIGAOR_LOCALITATE", "Localitate castigator", "ORAS_CASTIGATOR",
                    "Oras ofertant", "Oras"],
}
CONTRACT_IGNORED = {
    "Adresa castigator", "CASTIGATOR_ADRESA", "CastigatorAdresa", "CPVCodeID", "CPV_CODE_ID", "ContractPeriodic",
    "Cu fonduri comunitare?", "Cu subcontractare?", "DENUMIRE_NUTS", "DEPOZITE_GARANTII", "Depozite si garantii",
    "DepoziteGarantii", "FONDURI_COMUNITARE", "FOND_EUROPEAN", "Fond european", "FondEuropean", "FonduriComunitare",
    "MODALITATE_CONTRACTARE", "MODALITATE_DESFASURARE", "MODALITATI_FINANTARE", "Modalitate contractare",
    "Modalitate de desfasurare", "Modalitate finantare", "ModalitatiFinantare", "SUBCONTRACTAT", "Subcontractat",
    "TIP_FINANTARE", "TIP_LESIGLATIE", "Tip finantare", "Tip legislatie", "TipFinantare", "TipLegislatieID",
    "Valoare", "ValoareEUR",
}
NOTICE_ALIASES = {
    "notice_id": ["NumarAnunt", "Numar Anunt", "NUMAR_ANUNT_INVITATIE", "NUMAR_ANUNT", "Numar anunt",
                  "Numar anunt initiere"],
    "notice_date": ["DataPublicare", "Data Publicare", "DATA_PUBLICARE", "Data publicare"],
    "notice_type": ["TIP_ANUNT", "Tip anunt"],
    "authority_name": ["DenumireAC", "Denumire Autoritate contractanta", "DENUMIRE_AC", "AUTORITATE_CONTRACTANTA",
                       "Autoritate contractanta"],
    "authority_cui": ["CUI", "CUI_AC", "CUI_AUTORITATE", "CUI autoritate contractanta"],
    "county": ["Judet", "JUDET", "JUDET_AUTORITATE", "Judet autoritate"],
    "contract_type": ["TipContract", "Tip Contract", "TIP_CONTRACT", "Tip contract"],
    "procedure_type": ["TipProcedura", "Tip Procedura", "TIP_PROCEDURA", "Tip procedura"],
    "procedure_status": ["STARE_PROCEDURA", "Stare procedura"],
    "criterion": ["CriteriuAtribuire", "Criteriu Atribuire", "CRITERIU_ATRIBUIRE", "Criteriu de atribuire"],
    "estimated_value": ["ValoareEstimata", "Valoare Estimata", "VALOARE_ESTIMATA", "Valoare estimata",
                        "VALOARE_ESTIMATA_PROCEDURA", "Valoare estimata procedura",
                        "Valoare estimata procedura (RON)"],
    "estimated_currency": ["Moneda", "MONEDA", "MONEDA_PROCEDURA", "Moneda valoare estimata procedura", "Moneda.1"],
    "cpv_code": ["MainCPV", "Cod CPV", "MAIN_CPV_CODE", "COD_CPV_PROCEDURA"],
    "cpv_name": ["MainCPVName", "Denumire Cod CPV", "MAIN_CPV_NAME", "DENUMIRE_CPV_PROCEDURA", "Denumire CPV"],
    "lot_number": ["Numar lot"],
    "lot_value": ["Valoare estimata lot"],
    "procedure_title": ["DENUMIRE_PROCEDURA", "Denumire procedura", "Obiectul contractului"],
}
NOTICE_IGNORED = {
    "Anunt cu transmitere la JOUE?", "CU_LOTURI", "Contractul este impartit in loturi?", "Cu loturi?",
    "Cu transmitere JOUE?", "Cu transmitere la JOUE?", "Denumire lot", "Fonduri Comunitare", "Fonduri comunitare?",
    "FONDURI_COMUNITARE", "FonduriComunitare", "LOCALITATE_AUTORITATE", "Localitate", "Localitate autoritate",
    "MODALITATE_ATRIBUIRE", "MODALITATE_DESFASURARE", "Modalitate Desfasurare", "Modalitate de atribuire",
    "Modalitate de desfasurare", "ModalitateDesfasurare", "Nr.crt.", "TRANSMITERE_JOUE", "TRIMIS_OJEU",
    "Trimis la OJEU", "TrimisOJEU", "UTILITATI", "Utilitati", "Utilitati?",
}
SCHEMAS = {
    "contracts": (CONTRACT_ALIASES, CONTRACT_IGNORED),
    "notices": (NOTICE_ALIASES, NOTICE_IGNORED),
}


def normalize_cui(raw: Optional[str]) -> Optional[str]:
    """Reduce a tax code to one form: RO 123, RO123 and 123.0 all become 123."""
    if raw is None or pd.isna(raw):
        return None
    value = re.sub(r"\s+", "", str(raw)).upper()
    value = re.sub(r"\.0$", "", value)
    value = re.sub(r"^RO(?=\d)", "", value)
    return value or None


def standardize(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Return the frame with canonical columns. An unknown column raises ValueError."""
    aliases, ignored = SCHEMAS[kind]
    columns = {str(column).strip(): column for column in frame.columns}
    canonical_by_alias = {alias: name for name, names in aliases.items() for alias in names}
    unknown = [name for name in columns if name not in canonical_by_alias and name not in ignored]
    if unknown:
        raise ValueError(f"Unknown {kind} columns: {unknown}")
    # In 2016-2018 files "Moneda" is the contract currency, next to a dedicated estimate column.
    has_dedicated_currency = "MonedaValoareEstimataParticipare" in columns
    result = pd.DataFrame(index=frame.index)
    for name, names in aliases.items():
        present = [
            alias for alias in names
            if alias in columns and not (alias == "Moneda" and has_dedicated_currency and kind == "contracts")
        ]
        result[name] = frame[columns[present[0]]] if present else pd.Series(pd.NA, index=frame.index, dtype="object")
    for column in ("authority_cui", "winner_cui"):
        if column in result:
            result[column] = result[column].map(normalize_cui)
    return result
