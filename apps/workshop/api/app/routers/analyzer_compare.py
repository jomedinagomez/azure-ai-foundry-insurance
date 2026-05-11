# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import logging
import os
import time

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from helpers.azure_credential_utils import get_azure_credential

logger = logging.getLogger(__name__)

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
CU_API_VERSION = "2025-11-01"   # Content Understanding GA (default)
DI_API_VERSION = "2024-11-30"   # Document Intelligence v4.0 GA (default)
ANALYZER_COMPARE_TIMEOUT_SECONDS = int(os.environ.get("ANALYZER_COMPARE_TIMEOUT_SECONDS", "300"))

# All known API versions for each service (newest first)
DI_API_VERSIONS = [
    {"value": "2024-11-30",         "label": "2024-11-30 \u2014 GA v4.0"},
    {"value": "2024-07-31-preview", "label": "2024-07-31-preview \u2014 v4.0 Preview"},
    {"value": "2023-07-31",         "label": "2023-07-31 \u2014 GA v3.1"},
]
CU_API_VERSIONS = [
    {"value": "2025-11-01",         "label": "2025-11-01 \u2014 GA"},
    {"value": "2024-12-01-preview", "label": "2024-12-01-preview \u2014 Preview"},
]

_SHARED_ANALYZERS = None  # removed — DI and CU now have independent lists below

# ── Document Intelligence v4.0 prebuilt models (2024-11-30 GA)
# Source: https://learn.microsoft.com/azure/ai-services/document-intelligence/model-overview
DI_PREBUILT_ANALYZERS: list[dict] = [
    # Document Analysis
    {"id": "prebuilt-read",               "name": "Read",                       "category": "Document Analysis",  "description": "OCR — extracts printed and handwritten text from documents."},
    {"id": "prebuilt-layout",             "name": "Layout",                     "category": "Document Analysis",  "description": "Extracts text, tables, selection marks, headers, and document structure."},
    # Finance
    {"id": "prebuilt-invoice",            "name": "Invoice",                    "category": "Finance",            "description": "Extracts vendor, customer, amounts, due date, and line items."},
    {"id": "prebuilt-receipt",            "name": "Receipt",                    "category": "Finance",            "description": "Extracts merchant, date, totals, and line items from receipts."},
    {"id": "prebuilt-creditCard",         "name": "Credit Card",                "category": "Finance",            "description": "Extracts key fields from credit and debit cards."},
    {"id": "prebuilt-check.us",           "name": "US Bank Check",              "category": "Finance",            "description": "Extracts check details, account details, amount, and memo."},
    {"id": "prebuilt-bankStatement",      "name": "Bank Statement",             "category": "Finance",            "description": "Extracts account number, bank details, statement details, and transactions."},
    {"id": "prebuilt-payStub.us",         "name": "US Pay Stub",                "category": "Finance",            "description": "Extracts payroll key fields and line items from pay stubs."},
    # Identity
    {"id": "prebuilt-idDocument",              "name": "ID Document",           "category": "Identity",           "description": "Extracts fields from US driver's licenses and international passports."},
    {"id": "prebuilt-businessCard",            "name": "Business Card",         "category": "Identity",           "description": "Extracts contact information from business cards. (deprecated in v4.0)"},
    {"id": "prebuilt-healthInsuranceCard.us",  "name": "Health Insurance Card (US)", "category": "Identity",     "description": "Extracts fields from US health insurance cards."},
    # Tax (US)
    {"id": "prebuilt-tax.us.w2",               "name": "W-2",                  "category": "Tax (US)",           "description": "Wage and Tax Statement."},
    {"id": "prebuilt-tax.us.w4",               "name": "W-4",                  "category": "Tax (US)",           "description": "Employee's Withholding Certificate."},
    {"id": "prebuilt-tax.us.1040",             "name": "1040",                 "category": "Tax (US)",           "description": "US Individual Income Tax Return."},
    {"id": "prebuilt-tax.us.1040Senior",       "name": "1040 Senior",          "category": "Tax (US)",           "description": "US Individual Income Tax Return for senior taxpayers."},
    {"id": "prebuilt-tax.us.1040Schedule1",    "name": "1040 Schedule 1",      "category": "Tax (US)",           "description": "Additional Income and Adjustments to Income."},
    {"id": "prebuilt-tax.us.1040Schedule2",    "name": "1040 Schedule 2",      "category": "Tax (US)",           "description": "Additional Taxes."},
    {"id": "prebuilt-tax.us.1040Schedule3",    "name": "1040 Schedule 3",      "category": "Tax (US)",           "description": "Additional Credits and Payments."},
    {"id": "prebuilt-tax.us.1040ScheduleA",    "name": "1040 Schedule A",      "category": "Tax (US)",           "description": "Itemized Deductions."},
    {"id": "prebuilt-tax.us.1040ScheduleB",    "name": "1040 Schedule B",      "category": "Tax (US)",           "description": "Interest and Ordinary Dividends."},
    {"id": "prebuilt-tax.us.1040ScheduleC",    "name": "1040 Schedule C",      "category": "Tax (US)",           "description": "Profit or Loss from Business."},
    {"id": "prebuilt-tax.us.1040ScheduleD",    "name": "1040 Schedule D",      "category": "Tax (US)",           "description": "Capital Gains and Losses."},
    {"id": "prebuilt-tax.us.1040ScheduleE",    "name": "1040 Schedule E",      "category": "Tax (US)",           "description": "Supplemental Income and Loss."},
    {"id": "prebuilt-tax.us.1040ScheduleSE",   "name": "1040 Schedule SE",     "category": "Tax (US)",           "description": "Self-Employment Tax."},
    {"id": "prebuilt-tax.us.1095A",            "name": "1095-A",               "category": "Tax (US)",           "description": "Health Insurance Marketplace Statement."},
    {"id": "prebuilt-tax.us.1095C",            "name": "1095-C",               "category": "Tax (US)",           "description": "Employer-Provided Health Insurance Offer and Coverage."},
    {"id": "prebuilt-tax.us.1098",             "name": "1098",                 "category": "Tax (US)",           "description": "Mortgage Interest Statement."},
    {"id": "prebuilt-tax.us.1098E",            "name": "1098-E",               "category": "Tax (US)",           "description": "Student Loan Interest Statement."},
    {"id": "prebuilt-tax.us.1098T",            "name": "1098-T",               "category": "Tax (US)",           "description": "Tuition Statement."},
    {"id": "prebuilt-tax.us.1099NEC",          "name": "1099-NEC",             "category": "Tax (US)",           "description": "Nonemployee Compensation."},
    {"id": "prebuilt-tax.us.1099MISC",         "name": "1099-MISC",            "category": "Tax (US)",           "description": "Miscellaneous Income."},
    {"id": "prebuilt-tax.us.1099INT",          "name": "1099-INT",             "category": "Tax (US)",           "description": "Interest Income."},
    {"id": "prebuilt-tax.us.1099DIV",          "name": "1099-DIV",             "category": "Tax (US)",           "description": "Dividends and Distributions."},
    {"id": "prebuilt-tax.us.1099R",            "name": "1099-R",               "category": "Tax (US)",           "description": "Distributions from Pensions, Annuities, and Retirement Plans."},
    {"id": "prebuilt-tax.us.1099G",            "name": "1099-G",               "category": "Tax (US)",           "description": "Certain Government Payments."},
    {"id": "prebuilt-tax.us.1099SSA",          "name": "1099-SSA",             "category": "Tax (US)",           "description": "Social Security Benefit Statement."},
    # Mortgage (US)
    {"id": "prebuilt-mortgage.us.1003",                 "name": "Mortgage 1003",       "category": "Mortgage (US)", "description": "Uniform Residential Loan Application (URLA)."},
    {"id": "prebuilt-mortgage.us.1004",                 "name": "Mortgage 1004",       "category": "Mortgage (US)", "description": "Uniform Residential Appraisal Report (URAR)."},
    {"id": "prebuilt-mortgage.us.1005",                 "name": "Mortgage 1005",       "category": "Mortgage (US)", "description": "Verification of Employment."},
    {"id": "prebuilt-mortgage.us.1008",                 "name": "Mortgage 1008",       "category": "Mortgage (US)", "description": "Uniform Underwriting and Transmittal Summary."},
    {"id": "prebuilt-mortgage.us.closingDisclosure",    "name": "Closing Disclosure",  "category": "Mortgage (US)", "description": "Extracts closing costs, transaction costs, and loan details."},
    # Legal
    {"id": "prebuilt-contract",               "name": "Contract",               "category": "Legal",              "description": "Extracts parties, jurisdictions, contract ID, and title from contracts."},
    {"id": "prebuilt-marriageCertificate.us", "name": "US Marriage Certificate", "category": "Legal",              "description": "Extracts key fields from US marriage certificates."},
]

# ── Content Understanding prebuilt analyzers (2025-11-01 GA)
# Source: https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/prebuilt-analyzers
CU_PREBUILT_ANALYZERS: list[dict] = [
    # Content Extraction
    {"id": "prebuilt-read",              "name": "Read",                       "category": "Content Extraction",  "description": "Basic OCR — extracts words, paragraphs, formulas, and barcodes."},
    {"id": "prebuilt-layout",            "name": "Layout",                     "category": "Content Extraction",  "description": "Extracts text, tables, figures, sections, and layout structure as markdown."},
    # Base analyzers (parent for custom analyzers)
    {"id": "prebuilt-document",          "name": "Document (Base)",            "category": "Base",                "description": "Base document processing — use as parent when creating custom document analyzers."},
    {"id": "prebuilt-image",             "name": "Image (Base)",               "category": "Base",                "description": "Base image processing — use as parent when creating custom image analyzers."},
    {"id": "prebuilt-audio",             "name": "Audio (Base)",               "category": "Base",                "description": "Base audio processing — use as parent when creating custom audio analyzers."},
    {"id": "prebuilt-video",             "name": "Video (Base)",               "category": "Base",                "description": "Base video processing — use as parent when creating custom video analyzers."},
    # RAG / Search
    {"id": "prebuilt-documentSearch",    "name": "Document Search",            "category": "RAG / Search",        "description": "Extracts layout + figure descriptions as markdown — optimized for RAG ingestion."},
    {"id": "prebuilt-imageSearch",       "name": "Image Search",               "category": "RAG / Search",        "description": "Generates descriptions and insights from images for search and retrieval."},
    {"id": "prebuilt-audioSearch",       "name": "Audio Search",               "category": "RAG / Search",        "description": "Transcribes and summarizes conversations from audio/video for search."},
    {"id": "prebuilt-videoSearch",       "name": "Video Search",               "category": "RAG / Search",        "description": "Analyzes videos — extracts transcripts and scene descriptions per segment."},
    # Utility
    {"id": "prebuilt-documentFieldSchema","name": "Document Field Schema",     "category": "Utility",             "description": "Analyzes a document and proposes an appropriate field extraction schema."},
    {"id": "prebuilt-documentFields",    "name": "Document Fields",            "category": "Utility",             "description": "Extracts key-value pairs from documents as structured fields."},
    # Finance
    {"id": "prebuilt-invoice",           "name": "Invoice",                    "category": "Finance",             "description": "Extracts vendor, customer, amounts, and line items from invoices, utility bills, and orders."},
    {"id": "prebuilt-receipt",           "name": "Receipt",                    "category": "Finance",             "description": "Extracts merchant, totals, and line items from receipts."},
    {"id": "prebuilt-receipt.generic",   "name": "Receipt (Generic)",          "category": "Finance",             "description": "General sales receipt extraction."},
    {"id": "prebuilt-receipt.hotel",     "name": "Receipt (Hotel)",            "category": "Finance",             "description": "Hotel receipts and folios."},
    {"id": "prebuilt-creditCard",        "name": "Credit Card",                "category": "Finance",             "description": "Extracts key fields from credit card statements."},
    {"id": "prebuilt-creditMemo",        "name": "Credit Memo",                "category": "Finance",             "description": "Extracts fields from credit memos and refund documents."},
    {"id": "prebuilt-check.us",          "name": "US Bank Check",              "category": "Finance",             "description": "Extracts check details, account details, amount, and memo."},
    {"id": "prebuilt-bankStatement.us",  "name": "US Bank Statement",          "category": "Finance",             "description": "Extracts account number, bank details, statement details, and transactions."},
    # Identity
    {"id": "prebuilt-idDocument",              "name": "ID Document",          "category": "Identity",            "description": "Driver licenses, ID cards, passports, Social Security, military IDs, PAN/Aadhaar."},
    {"id": "prebuilt-idDocument.generic",      "name": "ID Document (Generic)","category": "Identity",            "description": "Generic identification documents from various regions worldwide."},
    {"id": "prebuilt-idDocument.passport",     "name": "Passport",             "category": "Identity",            "description": "Passport books and passport cards (worldwide)."},
    {"id": "prebuilt-healthInsuranceCard.us",  "name": "Health Insurance Card (US)", "category": "Identity",      "description": "Extracts fields from US health insurance cards."},
    # Tax (US)
    {"id": "prebuilt-tax.us",                  "name": "US Tax (General)",     "category": "Tax (US)",            "description": "General US tax form classifier and extractor."},
    {"id": "prebuilt-tax.us.w2",               "name": "W-2",                  "category": "Tax (US)",            "description": "Wage and Tax Statement."},
    {"id": "prebuilt-tax.us.w4",               "name": "W-4",                  "category": "Tax (US)",            "description": "Employee's Withholding Certificate."},
    {"id": "prebuilt-tax.us.1040",             "name": "1040",                 "category": "Tax (US)",            "description": "US Individual Income Tax Return."},
    {"id": "prebuilt-tax.us.1040Senior",       "name": "1040 Senior",          "category": "Tax (US)",            "description": "Form 1040 for senior taxpayers."},
    {"id": "prebuilt-tax.us.1040Schedule1",    "name": "1040 Schedule 1",      "category": "Tax (US)",            "description": "Additional Income and Adjustments to Income."},
    {"id": "prebuilt-tax.us.1040Schedule2",    "name": "1040 Schedule 2",      "category": "Tax (US)",            "description": "Additional Taxes."},
    {"id": "prebuilt-tax.us.1040Schedule3",    "name": "1040 Schedule 3",      "category": "Tax (US)",            "description": "Additional Credits and Payments."},
    {"id": "prebuilt-tax.us.1040Schedule8812", "name": "1040 Schedule 8812",   "category": "Tax (US)",            "description": "Credits for Qualifying Children and Other Dependents."},
    {"id": "prebuilt-tax.us.1040ScheduleA",    "name": "1040 Schedule A",      "category": "Tax (US)",            "description": "Itemized Deductions."},
    {"id": "prebuilt-tax.us.1040ScheduleB",    "name": "1040 Schedule B",      "category": "Tax (US)",            "description": "Interest and Ordinary Dividends."},
    {"id": "prebuilt-tax.us.1040ScheduleC",    "name": "1040 Schedule C",      "category": "Tax (US)",            "description": "Profit or Loss from Business."},
    {"id": "prebuilt-tax.us.1040ScheduleD",    "name": "1040 Schedule D",      "category": "Tax (US)",            "description": "Capital Gains and Losses."},
    {"id": "prebuilt-tax.us.1040ScheduleE",    "name": "1040 Schedule E",      "category": "Tax (US)",            "description": "Supplemental Income and Loss."},
    {"id": "prebuilt-tax.us.1040ScheduleEIC",  "name": "1040 Schedule EIC",    "category": "Tax (US)",            "description": "Earned Income Credit."},
    {"id": "prebuilt-tax.us.1040ScheduleF",    "name": "1040 Schedule F",      "category": "Tax (US)",            "description": "Profit or Loss from Farming."},
    {"id": "prebuilt-tax.us.1040ScheduleH",    "name": "1040 Schedule H",      "category": "Tax (US)",            "description": "Household Employment Taxes."},
    {"id": "prebuilt-tax.us.1040ScheduleJ",    "name": "1040 Schedule J",      "category": "Tax (US)",            "description": "Income Averaging for Farmers and Fishermen."},
    {"id": "prebuilt-tax.us.1040ScheduleR",    "name": "1040 Schedule R",      "category": "Tax (US)",            "description": "Credit for the Elderly or Disabled."},
    {"id": "prebuilt-tax.us.1040ScheduleSE",   "name": "1040 Schedule SE",     "category": "Tax (US)",            "description": "Self-Employment Tax."},
    {"id": "prebuilt-tax.us.1095A",            "name": "1095-A",               "category": "Tax (US)",            "description": "Health Insurance Marketplace Statement."},
    {"id": "prebuilt-tax.us.1095C",            "name": "1095-C",               "category": "Tax (US)",            "description": "Employer-Provided Health Insurance."},
    {"id": "prebuilt-tax.us.1098",             "name": "1098",                 "category": "Tax (US)",            "description": "Mortgage Interest Statement."},
    {"id": "prebuilt-tax.us.1098E",            "name": "1098-E",               "category": "Tax (US)",            "description": "Student Loan Interest Statement."},
    {"id": "prebuilt-tax.us.1098T",            "name": "1098-T",               "category": "Tax (US)",            "description": "Tuition Statement."},
    {"id": "prebuilt-tax.us.1099Combo",        "name": "1099 Combo",           "category": "Tax (US)",            "description": "Combined 1099 forms."},
    {"id": "prebuilt-tax.us.1099A",            "name": "1099-A",               "category": "Tax (US)",            "description": "Acquisition or Abandonment of Secured Property."},
    {"id": "prebuilt-tax.us.1099B",            "name": "1099-B",               "category": "Tax (US)",            "description": "Proceeds from Broker and Barter Exchange Transactions."},
    {"id": "prebuilt-tax.us.1099C",            "name": "1099-C",               "category": "Tax (US)",            "description": "Cancellation of Debt."},
    {"id": "prebuilt-tax.us.1099CAP",          "name": "1099-CAP",             "category": "Tax (US)",            "description": "Changes in Corporate Control and Capital Structure."},
    {"id": "prebuilt-tax.us.1099DA",           "name": "1099-DA",              "category": "Tax (US)",            "description": "Digital Asset Proceeds from Broker Transactions."},
    {"id": "prebuilt-tax.us.1099DIV",          "name": "1099-DIV",             "category": "Tax (US)",            "description": "Dividends and Distributions."},
    {"id": "prebuilt-tax.us.1099G",            "name": "1099-G",               "category": "Tax (US)",            "description": "Certain Government Payments."},
    {"id": "prebuilt-tax.us.1099H",            "name": "1099-H",               "category": "Tax (US)",            "description": "Health Coverage Tax Credit Advance Payments."},
    {"id": "prebuilt-tax.us.1099INT",          "name": "1099-INT",             "category": "Tax (US)",            "description": "Interest Income."},
    {"id": "prebuilt-tax.us.1099K",            "name": "1099-K",               "category": "Tax (US)",            "description": "Payment Card and Third Party Network Transactions."},
    {"id": "prebuilt-tax.us.1099LS",           "name": "1099-LS",              "category": "Tax (US)",            "description": "Reportable Life Insurance Sale."},
    {"id": "prebuilt-tax.us.1099LTC",          "name": "1099-LTC",             "category": "Tax (US)",            "description": "Long-Term Care and Accelerated Death Benefits."},
    {"id": "prebuilt-tax.us.1099MISC",         "name": "1099-MISC",            "category": "Tax (US)",            "description": "Miscellaneous Income."},
    {"id": "prebuilt-tax.us.1099NEC",          "name": "1099-NEC",             "category": "Tax (US)",            "description": "Nonemployee Compensation."},
    {"id": "prebuilt-tax.us.1099OID",          "name": "1099-OID",             "category": "Tax (US)",            "description": "Original Issue Discount."},
    {"id": "prebuilt-tax.us.1099PATR",         "name": "1099-PATR",            "category": "Tax (US)",            "description": "Taxable Distributions Received from Cooperatives."},
    {"id": "prebuilt-tax.us.1099Q",            "name": "1099-Q",               "category": "Tax (US)",            "description": "Payments from Qualified Education Programs."},
    {"id": "prebuilt-tax.us.1099QA",           "name": "1099-QA",              "category": "Tax (US)",            "description": "Distributions from ABLE Accounts."},
    {"id": "prebuilt-tax.us.1099R",            "name": "1099-R",               "category": "Tax (US)",            "description": "Distributions from Pensions, Annuities, and Retirement Plans."},
    {"id": "prebuilt-tax.us.1099S",            "name": "1099-S",               "category": "Tax (US)",            "description": "Proceeds from Real Estate Transactions."},
    {"id": "prebuilt-tax.us.1099SA",           "name": "1099-SA",              "category": "Tax (US)",            "description": "Distributions from HSA, Archer MSA, or Medicare Advantage MSA."},
    {"id": "prebuilt-tax.us.1099SB",           "name": "1099-SB",              "category": "Tax (US)",            "description": "Seller's Investment in Life Insurance Contract."},
    {"id": "prebuilt-tax.us.1099SSA",          "name": "1099-SSA",             "category": "Tax (US)",            "description": "Social Security Benefit Statement."},
    # Mortgage (US)
    {"id": "prebuilt-mortgage.us",                      "name": "Mortgage (General)", "category": "Mortgage (US)", "description": "General US mortgage document extraction."},
    {"id": "prebuilt-mortgage.us.1003",                 "name": "Mortgage 1003",      "category": "Mortgage (US)", "description": "Uniform Residential Loan Application (URLA)."},
    {"id": "prebuilt-mortgage.us.1004",                 "name": "Mortgage 1004",      "category": "Mortgage (US)", "description": "Uniform Residential Appraisal Report (URAR)."},
    {"id": "prebuilt-mortgage.us.1005",                 "name": "Mortgage 1005",      "category": "Mortgage (US)", "description": "Verification of Employment."},
    {"id": "prebuilt-mortgage.us.1008",                 "name": "Mortgage 1008",      "category": "Mortgage (US)", "description": "Uniform Underwriting and Transmittal Summary."},
    {"id": "prebuilt-mortgage.us.closingDisclosure",    "name": "Closing Disclosure", "category": "Mortgage (US)", "description": "Extracts closing costs, transaction costs, and loan details."},
    # Legal & Business
    {"id": "prebuilt-contract",               "name": "Contract",               "category": "Legal & Business",   "description": "Extracts parties, jurisdictions, contract ID, and title from business contracts."},
    {"id": "prebuilt-marriageCertificate.us", "name": "US Marriage Certificate", "category": "Legal & Business",   "description": "Extracts key fields from US marriage certificates."},
    # Procurement
    {"id": "prebuilt-procurement",    "name": "Procurement",                    "category": "Procurement",         "description": "Purchase orders, invoices, and procurement-related documents."},
    {"id": "prebuilt-purchaseOrder",  "name": "Purchase Order",                 "category": "Procurement",         "description": "Extracts vendor info, line items, pricing, and terms from purchase orders."},
    # Other
    {"id": "prebuilt-payStub.us",     "name": "US Pay Stub",                    "category": "Other",               "description": "Extracts key fields and line items from US pay stubs and earnings statements."},
    {"id": "prebuilt-utilityBill",    "name": "Utility Bill",                   "category": "Other",               "description": "Extracts account info, usage details, and payment data from utility bills."},
]

# Stamp source field on each entry
for _a in DI_PREBUILT_ANALYZERS:
    _a.setdefault("source", "di")
for _a in CU_PREBUILT_ANALYZERS:
    _a.setdefault("source", "cu")

ALL_ANALYZERS = DI_PREBUILT_ANALYZERS + CU_PREBUILT_ANALYZERS
PREBUILT_ANALYZERS = ALL_ANALYZERS  # back-compat alias

_DI_VALID_IDS = {a["id"] for a in DI_PREBUILT_ANALYZERS}
_CU_VALID_IDS = {a["id"] for a in CU_PREBUILT_ANALYZERS}




def _parse_error_message(status_code: int, response_text: str) -> str:
    """Extract a human-readable error message from an API error response body."""
    import json as _json
    try:
        body = _json.loads(response_text)
        err = body.get("error", {})
        inner = err.get("innererror", {})
        inner_code = inner.get("code", "")
        inner_msg  = inner.get("message", "")
        outer_msg  = err.get("message", "")
        if inner_code == "DefaultsNotSet":
            return (
                "This analyzer requires default model deployments to be configured. "
                "Call PATCH /contentunderstanding/defaults on your Content Understanding "
                "resource to set up the required LLM connections before using this analyzer."
            )
        if inner_code == "ContentEmpty":
            return "The service could not extract content from the uploaded file. Ensure the file is a supported format and is not empty or corrupt."
        if inner_msg:
            return f"{inner_code}: {inner_msg}" if inner_code else inner_msg
        if outer_msg:
            return outer_msg
    except Exception:
        pass
    return f"HTTP {status_code}: {response_text[:400]}"


def _normalize_operation_status(status: str) -> str:
    return "".join(ch for ch in str(status).lower() if ch.isalpha())


def _normalize_cognitive_endpoint(endpoint: str) -> str:
    value = (endpoint or "").strip().rstrip("/")
    if not value:
        return value
    if ".openai.azure.com" in value:
        value = value.replace(".openai.azure.com", ".cognitiveservices.azure.com")
        if value.endswith("/openai"):
            value = value[:-7]
    return value


router = APIRouter(
    prefix="/analyzer-compare",
    tags=["analyzer-compare"],
    responses={404: {"description": "Not found"}},
)


def _get_cu_headers(endpoint: str) -> dict:
    """Get auth headers for Content Understanding API calls."""
    credential = get_azure_credential()
    token = credential.get_token(COGNITIVE_SERVICES_SCOPE).token
    return {
        "Authorization": f"Bearer {token}",
        "x-ms-useragent": "cps-analyzer-compare/client",
    }


async def _run_single_analyzer(
    endpoint: str,
    analyzer_id: str,
    file_bytes: bytes,
    content_type: str,
    timeout: int = ANALYZER_COMPARE_TIMEOUT_SECONDS,
    api_version: str = CU_API_VERSION,
) -> dict:
    """
    Run a single Content Understanding analyzer against a file and poll for results.
    Returns a dict with keys: analyzer_id, status, result, error.
    """
    run_started = time.time()

    def _with_elapsed(payload: dict) -> dict:
        return {**payload, "elapsed_ms": int((time.time() - run_started) * 1000)}

    headers = _get_cu_headers(endpoint)
    # In the 2025-11-01 GA release, binary uploads moved from :analyze to :analyzeBinary.
    # Preview versions (2024-12-01-preview and earlier) still use :analyze with binary body.
    operation = "analyzeBinary" if api_version == "2025-11-01" else "analyze"
    analyze_url = (
        f"{endpoint.rstrip('/')}/contentunderstanding/analyzers"
        f"/{analyzer_id}:{operation}?api-version={api_version}"
    )

    upload_headers = dict(headers)
    upload_headers["Content-Type"] = "application/octet-stream"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(
                analyze_url,
                headers=upload_headers,
                content=file_bytes,
            )
            if response.status_code not in (200, 202):
                return _with_elapsed({
                    "analyzer_id": analyzer_id,
                    "status": "failed",
                    "result": None,
                    "error": _parse_error_message(response.status_code, response.text),
                })

            if response.status_code == 200:
                return _with_elapsed({
                    "analyzer_id": analyzer_id,
                    "status": "succeeded",
                    "result": response.json(),
                    "error": None,
                })

            operation_location = response.headers.get("operation-location", "")
            if not operation_location:
                return _with_elapsed({
                    "analyzer_id": analyzer_id,
                    "status": "failed",
                    "result": None,
                    "error": "Operation location header not found.",
                })

            # Use operation-location as returned by the service because it may include
            # additional query parameters required for polling.
            poll_url = operation_location
            if "api-version=" not in poll_url:
                sep = "&" if "?" in poll_url else "?"
                poll_url = f"{poll_url}{sep}api-version={api_version}"

            start = time.time()
            while True:
                if time.time() - start > timeout:
                    return _with_elapsed({
                        "analyzer_id": analyzer_id,
                        "status": "failed",
                        "result": None,
                        "error": f"Timed out after {timeout} seconds.",
                    })

                poll_resp = await client.get(poll_url, headers=headers)
                poll_resp.raise_for_status()
                data = poll_resp.json()
                status = _normalize_operation_status(data.get("status", ""))
                logger.debug(f"Analyzer {analyzer_id} poll status: {status}")

                if status in ("succeeded", "partiallysucceeded"):
                    return _with_elapsed({
                        "analyzer_id": analyzer_id,
                        "status": "succeeded",
                        "result": data,
                        "error": None,
                    })
                elif status in ("failed", "canceled", "cancelled"):
                    return _with_elapsed({
                        "analyzer_id": analyzer_id,
                        "status": "failed",
                        "result": None,
                        "error": _parse_error_message(poll_resp.status_code, poll_resp.text),
                    })
                elif status in ("running", "notstarted", "not started"):
                    await asyncio.sleep(2)
                else:
                    # Unexpected status — log and keep waiting
                    logger.warning(f"Analyzer {analyzer_id} unexpected poll status '{status}': {poll_resp.text[:200]}")
                    await asyncio.sleep(2)

    except Exception as exc:
        logger.error(f"Analyzer {analyzer_id} failed: {exc}")
        return _with_elapsed({
            "analyzer_id": analyzer_id,
            "status": "failed",
            "result": None,
            "error": str(exc),
        })


async def _run_di_analyzer(
    endpoint: str,
    model_id: str,
    file_bytes: bytes,
    content_type: str,
    timeout: int = ANALYZER_COMPARE_TIMEOUT_SECONDS,
    api_version: str = DI_API_VERSION,
) -> dict:
    """
    Run a single Document Intelligence prebuilt model and poll for results.
    Returns a dict with keys: analyzer_id, status, result, error.
    """
    run_started = time.time()

    def _with_elapsed(payload: dict) -> dict:
        return {**payload, "elapsed_ms": int((time.time() - run_started) * 1000)}

    headers = _get_cu_headers(endpoint)
    analyze_url = (
        f"{endpoint.rstrip('/')}/documentintelligence/documentModels"
        f"/{model_id}:analyze?api-version={api_version}&outputContentFormat=markdown"
    )
    upload_headers = dict(headers)
    upload_headers["Content-Type"] = "application/octet-stream"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(analyze_url, headers=upload_headers, content=file_bytes)
            if response.status_code not in (200, 202):
                return _with_elapsed({
                    "analyzer_id": model_id,
                    "status": "failed",
                    "result": None,
                    "error": _parse_error_message(response.status_code, response.text),
                })
            if response.status_code == 200:
                return _with_elapsed({"analyzer_id": model_id, "status": "succeeded", "result": response.json(), "error": None})

            operation_location = response.headers.get("operation-location", "")
            if not operation_location:
                return _with_elapsed({"analyzer_id": model_id, "status": "failed", "result": None, "error": "Operation location header not found."})

            poll_url = operation_location
            if "api-version=" not in poll_url:
                sep = "&" if "?" in poll_url else "?"
                poll_url = f"{poll_url}{sep}api-version={api_version}"

            start = time.time()
            while True:
                if time.time() - start > timeout:
                    return _with_elapsed({"analyzer_id": model_id, "status": "failed", "result": None, "error": f"Timed out after {timeout}s."})

                poll_resp = await client.get(poll_url, headers=headers)
                poll_resp.raise_for_status()
                data = poll_resp.json()
                status = _normalize_operation_status(data.get("status", ""))

                if status in ("succeeded", "partiallysucceeded"):
                    return _with_elapsed({"analyzer_id": model_id, "status": "succeeded", "result": data, "error": None})
                if status in ("failed", "canceled", "cancelled"):
                    return _with_elapsed({"analyzer_id": model_id, "status": "failed", "result": None,
                            "error": data.get("error", {}).get("message", "Unknown error")})
                await asyncio.sleep(2)

    except Exception as exc:
        logger.error(f"DI analyzer {model_id} failed: {exc}")
        return _with_elapsed({"analyzer_id": model_id, "status": "failed", "result": None, "error": str(exc)})


@router.get("/analyzers")
async def list_prebuilt_analyzers() -> list[dict]:
    """Returns the list of supported prebuilt analyzers (both DI and CU)."""
    return ALL_ANALYZERS


@router.get("/api-versions")
async def list_api_versions() -> dict:
    """Returns all known API versions for Document Intelligence and Content Understanding."""
    return {"di": DI_API_VERSIONS, "cu": CU_API_VERSIONS}


@router.post("/analyze")
async def compare_analyzers(
    analyzer_ids: str = Form(
        ...,
        description="Comma-separated list of '{source}:{id}' pairs, e.g. di:prebuilt-invoice,cu:prebuilt-invoice",
    ),
    file: UploadFile = File(..., description="Document to analyze (PDF or image)"),
    di_api_version: str = Form(DI_API_VERSION, description="API version for Document Intelligence calls"),
    cu_api_version: str = Form(CU_API_VERSION, description="API version for Content Understanding calls"),
    timeout_seconds: int = Form(ANALYZER_COMPARE_TIMEOUT_SECONDS, description="Polling timeout in seconds for each analyzer run"),
) -> JSONResponse:
    """
    Run multiple prebuilt analyzers (DI and/or CU) on the same document in parallel.
    Each analyzer_id should be prefixed with 'di:' or 'cu:'.
    """
    endpoint = os.environ.get("app_content_understanding_endpoint") or os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT", "")
    endpoint = _normalize_cognitive_endpoint(endpoint)
    if not endpoint:
        raise HTTPException(status_code=503, detail="Content Understanding endpoint is not configured.")

    # Parse "{source}:{id}" — fall back to "cu" for un-prefixed IDs (backward compat)
    requested: list[tuple[str, str]] = []
    for item in analyzer_ids.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            source, aid = item.split(":", 1)
        else:
            source, aid = "cu", item
        requested.append((source.lower(), aid))

    if not requested:
        raise HTTPException(status_code=400, detail="No analyzer IDs provided.")

    if timeout_seconds < 30:
        raise HTTPException(status_code=400, detail="timeout_seconds must be at least 30.")

    unknown = [
        aid for source, aid in requested
        if (source == "di" and aid not in _DI_VALID_IDS)
        or (source == "cu" and aid not in _CU_VALID_IDS)
    ]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown analyzer ID(s): {', '.join(unknown)}")

    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    tasks = [
        _run_di_analyzer(endpoint, aid, file_bytes, content_type, timeout=timeout_seconds, api_version=di_api_version)
        if source == "di"
        else _run_single_analyzer(endpoint, aid, file_bytes, content_type, timeout=timeout_seconds, api_version=cu_api_version)
        for source, aid in requested
    ]
    raw_results = await asyncio.gather(*tasks)

    # Prefix analyzer_id with source and record which API version was used
    results = [
        {**r, "analyzer_id": f"{source}:{r['analyzer_id']}",
         "api_version": di_api_version if source == "di" else cu_api_version}
        for (source, _), r in zip(requested, raw_results)
    ]

    return JSONResponse(content={"file_name": file.filename, "results": results})
