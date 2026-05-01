"""Canada Evidence Act s.31.6 Certificate of Authenticity — data + renderer.

Used by the export pipeline to attach a self-authentication block to
every Court Bundle PDF.
"""
from dataclasses import dataclass, field
from datetime import date
from html import escape


@dataclass
class ExhibitRecord:
    ref: str                        # e.g. "A" or "1"
    description: str
    source: str                     # e.g. "WhatsApp chat with X, 2024-03-14"
    ingested_at: str                # ISO date
    sha256: str


@dataclass
class CertificateInput:
    operator_name: str
    operator_address: str
    location: str
    signing_date: date
    software_version: str
    exhibits: list[ExhibitRecord] = field(default_factory=list)


_TEMPLATE = """\
<section class="auth-cert">
  <h2>CERTIFICATE OF AUTHENTICITY</h2>
  <p class="cert-statute"><em>Canada Evidence Act</em>, R.S.C. 1985, c. C-5,
  s. 31.6</p>

  <p>I, <strong>{name}</strong>, residing at {address}, CERTIFY that:</p>

  <ol class="cert-clauses">
    <li>The electronic documents listed in the Schedule below were extracted
        from the source(s) identified by the operation of {software}, an
        electronic documents system.</li>
    <li>The system was operating properly at the relevant time of
        extraction.</li>
    <li>Each electronic document is identified by its SHA-256 hash, computed
        at the time of ingestion. Each hash matches the file as held by the
        system at the time of this certification.</li>
    <li>The electronic documents have not been modified since ingestion.</li>
    <li>The integrity of the electronic documents system can be verified by
        the system's audit log, which is hash-chained from genesis.</li>
  </ol>

  <p>DATED at {location} this _____ day of ____________, {year}.</p>

  <p class="cert-signature">______________________________<br>
  Signature of {name}</p>

  <h3 class="cert-schedule-heading">Schedule of Electronic Documents</h3>
  <table class="cert-schedule">
    <thead>
      <tr><th>Exhibit</th><th>Description</th><th>Source</th>
          <th>Ingested</th><th>SHA-256</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</section>
"""


def render_certificate_html(c: CertificateInput) -> str:
    rows = []
    for x in c.exhibits:
        rows.append(
            f"<tr><td>Exhibit {escape(x.ref)}</td>"
            f"<td>{escape(x.description)}</td>"
            f"<td>{escape(x.source)}</td>"
            f"<td>{escape(x.ingested_at)}</td>"
            f"<td><code>{escape(x.sha256)}</code></td></tr>"
        )
    return _TEMPLATE.format(
        name=escape(c.operator_name),
        address=escape(c.operator_address),
        location=escape(c.location),
        year=c.signing_date.year,
        software=escape(c.software_version),
        rows="\n      ".join(rows),
    )
