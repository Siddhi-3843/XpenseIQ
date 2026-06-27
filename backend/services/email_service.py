import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL     = "XpenseIQ <onboarding@resend.dev>"


def send_verification_email(
    to_email: str,
    expense_id: int,
    vendor_name: str,
    total_amount: float,
    status: str,
    verifier_name: str,
    rejection_reason: str = None,
    transaction_date: str = None,
) -> dict:
    try:
        verified_at   = datetime.now().strftime("%d %b %Y, %I:%M %p")
        status_color  = "#22C55E" if status == "approved" else "#EF4444"
        status_label  = "Approved" if status == "approved" else "Rejected"
        status_icon   = "✅" if status == "approved" else "❌"

        rejection_row = ""
        if status == "rejected" and rejection_reason:
            rejection_row = f"""
            <tr>
              <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;border-bottom:1px solid #F0DCE4;">
                Rejection Reason
              </td>
              <td style="padding:10px 16px;font-weight:600;color:#EF4444;font-size:13px;border-bottom:1px solid #F0DCE4;">
                {rejection_reason}
              </td>
            </tr>"""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="margin:0;padding:0;background:#FDF4F7;font-family:Arial,sans-serif;">
          <div style="max-width:560px;margin:40px auto;background:#ffffff;
               border-radius:16px;border:1px solid #F0DCE4;
               box-shadow:0 4px 24px rgba(45,27,46,0.08);overflow:hidden;">

            <div style="background:linear-gradient(135deg,#E91E63,#AA225B);
                 padding:28px 32px;text-align:center;">
              <div style="font-size:24px;font-weight:800;color:#ffffff;">XpenseIQ</div>
              <div style="font-size:13px;color:rgba(255,255,255,0.85);margin-top:4px;">
                AI-Powered Smart Expense Scanner
              </div>
            </div>

            <div style="background:{status_color}15;border-bottom:3px solid {status_color};
                 padding:20px 32px;text-align:center;">
              <div style="font-size:28px;margin-bottom:6px;">{status_icon}</div>
              <div style="font-size:20px;font-weight:700;color:{status_color};">
                Expense {status_label}
              </div>
              <div style="font-size:13px;color:#8A6D7C;margin-top:4px;">
                Your expense has been reviewed and {status_label.lower()}.
              </div>
            </div>

            <div style="padding:24px 32px 8px;">
              <table style="width:100%;border-collapse:collapse;border:1px solid #F0DCE4;">
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;width:40%;">
                    Expense ID
                  </td>
                  <td style="padding:10px 16px;font-weight:600;color:#2D1B2E;font-size:13px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    #{expense_id}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;border-bottom:1px solid #F0DCE4;">
                    Vendor
                  </td>
                  <td style="padding:10px 16px;font-weight:600;color:#2D1B2E;font-size:13px;border-bottom:1px solid #F0DCE4;">
                    {vendor_name or 'N/A'}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    Amount
                  </td>
                  <td style="padding:10px 16px;font-weight:700;color:#E91E63;font-size:14px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    Rs {total_amount:,.2f}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;border-bottom:1px solid #F0DCE4;">
                    Transaction Date
                  </td>
                  <td style="padding:10px 16px;font-weight:600;color:#2D1B2E;font-size:13px;border-bottom:1px solid #F0DCE4;">
                    {transaction_date or 'N/A'}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    Status
                  </td>
                  <td style="padding:10px 16px;background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    <span style="background:{status_color}20;color:{status_color};
                          padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;">
                      {status_label}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;border-bottom:1px solid #F0DCE4;">
                    Verified By
                  </td>
                  <td style="padding:10px 16px;font-weight:600;color:#2D1B2E;font-size:13px;border-bottom:1px solid #F0DCE4;">
                    {verifier_name}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 16px;color:#8A6D7C;font-size:13px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    Verification Date
                  </td>
                  <td style="padding:10px 16px;font-weight:600;color:#2D1B2E;font-size:13px;
                       background:#FCF7F9;border-bottom:1px solid #F0DCE4;">
                    {verified_at}
                  </td>
                </tr>
                {rejection_row}
              </table>
            </div>

            <div style="padding:24px 32px;text-align:center;border-top:1px solid #F0DCE4;margin-top:16px;">
              <div style="font-size:12px;color:#8A6D7C;">
                This is an automated notification from
                <strong style="color:#E91E63;">XpenseIQ</strong>.
                Please do not reply to this email.
              </div>
            </div>
          </div>
        </body>
        </html>
        """

        payload = json.dumps({
            "from":    FROM_EMAIL,
            "to":      [to_email],
            "subject": f"XpenseIQ — Expense #{expense_id} {status_label}",
            "html":    html,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"RESEND SUCCESS: {resp_body}")
            return {"success": True}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"RESEND HTTP ERROR {e.code}: {error_body}")
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        print(f"RESEND ERROR: {str(e)}")
        return {"success": False, "error": str(e)}