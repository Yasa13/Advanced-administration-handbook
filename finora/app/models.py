from dataclasses import dataclass


@dataclass
class Classification:
    document_type: str = "Sonstiges"
    correspondent: str = "Unklar"
    addressee_type: str = "Unklar"
    addressee_name: str = ""
    private_person: str = ""
    document_date: str = ""
    invoice_number: str = ""
    reference_number: str = ""
    gross_amount: str = ""
    title: str = ""
    target_folder: str = ""
    confidence_document_type: float = 0.0
    confidence_correspondent: float = 0.0
    confidence_addressee: float = 0.0
    learned_from_history: bool = False
    learning_note: str = ""
