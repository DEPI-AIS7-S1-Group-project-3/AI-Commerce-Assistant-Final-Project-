from pydantic import BaseModel


class PolicySummaryOut(BaseModel):
    slug: str
    category: str
    title_ar: str
    version: str


class PolicySection(BaseModel):
    no: int
    title: str
    body: str


class PolicyOut(PolicySummaryOut):
    body_md: str
    sections: list[PolicySection]
