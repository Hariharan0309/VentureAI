import io
import json
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

import firebase_admin
from firebase_admin import credentials, storage

# Initialize Firebase once (use your service account)
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        "storageBucket": "your-project-id.appspot.com"
    })

def generate_pdf_from_json(json_data):
    """Generate PDF as bytes (no file saving)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    def add_section(title, content, level=1):
        if title:
            style = styles["Heading1"] if level == 1 else styles["Heading2"]
            story.append(Paragraph(title, style))
        story.append(Spacer(1, 8))

        if isinstance(content, dict):
            for k, v in content.items():
                add_section(k.replace("_", " ").title(), v, level + 1)
        elif isinstance(content, list):
            for item in content:
                add_section(None, item, level + 1)
        else:
            story.append(Paragraph(str(content), styles["Normal"]))
            story.append(Spacer(1, 6))

    add_section("Investment Memo", json_data["investment_memo"])
    doc.build(story)

    buffer.seek(0)
    return buffer

def upload_pdf_to_firebase(pdf_buffer, remote_path):
    """Upload in-memory PDF buffer to Firebase Storage and return public URL."""
    bucket = storage.bucket()
    blob = bucket.blob(remote_path)

    # Upload from memory
    blob.upload_from_file(pdf_buffer, content_type="application/pdf")

    # Make it public
    blob.make_public()

    return blob.public_url

# Example usage
data = { "investment_memo": { "company_name": "Sia (Datastride Analytics)", "date": "2024-05-17", "author": "report_generation_agent", "executive_summary": { "introduction": "Sia is an Agentic AI platform for data analytics, offering a conversational chat interface to help enterprises overcome the complexity and high cost of traditional data analysis. By democratizing data access, Sia enables non-technical users to generate insights, visualizations, and reports instantly.", "opportunity": "The Global Data Analytics market is a $300B industry plagued by project failures (~90%) due to dependency on slow, centralized data teams and fragmented systems. Sia targets the emerging 'Agentic AI' segment, a Serviceable Obtainable Market (SOM) projected to grow from $5B in 2024 to $200B by 2034, with an aggressive 43% CAGR.", "key_strengths": "The company's strengths lie in its cohesive and experienced founding team (8+ years together, 10 patents), significant early traction with blue-chip clients (Bosch, Mercedes-Benz), a clear B2B business model with high contract values ($150k-$300k ACV), and a strong product vision.", "the_ask": "Sia is seeking a Seed round of INR 5 Crores to scale its Sales & Marketing (60%) and Product Development (30%).", "recommendation": "Recommendation to proceed with due diligence. Sia presents a compelling investment opportunity with a proven team, validated market need, and strong initial traction. Key areas for diligence include verifying the technology, assessing the competitive landscape, and validating the sales cycle and scalability of the GTM strategy." }, "company_overview": { "product": "A 'Simple Chat Interface' that acts as an Agentic AI layer over a company's fragmented data sources.", "mission": "To help businesses 'Drive value with Data from a conversation' by democratizing data analytics and making it accessible to everyone in an organization.", "vision": "To evolve from a community-driven tool for mass adoption (2025-26) into a fully autonomous AI agent that drives decisions at the leadership level (2029-30)." }, "problem_and_market_opportunity": { "problem": "Enterprises face an 'AI Crisis' where 90% of AI projects fail. This is caused by a dependency on centralized data teams, which creates bottlenecks, talent shortages, and high costs. Data remains siloed (68% unused) and analytics processes are fragile and slow.", "market_size": { "tam": "$300 Billion (Global Data Analytics)", "som": "$5 Billion in 2024, growing to $200 Billion by 2034 (Agentic AI Market)" }, "market_validation": "Gartner predicts that by 2025, 80% of enterprises will utilize AI-driven analytics. The company has identified a clear pain point and is positioning itself in a high-growth niche within a massive market." }, "solution_and_product": { "product_description": "Sia connects to disparate data systems and provides a unified, conversational interface. It allows users to ask questions in natural language and receive instant insights, automated charts, data summaries, and even build no-code models.", "key_features": [ "Conversational AI for data queries", "Automated charts and visualizations", "Unified Data Integration across various sources (Cloud, FTP, HTTP)", "Instant insights and report generation", "No-code model building" ], "impact_metrics": "Client deployments show significant improvements over conventional systems: Time-to-insight reduced from days to <5 minutes (90% quicker), budget reduced by 4x, and project deployment time cut by 80%." }, "team": { "founders": "Divya Krishna R, Sumalata Kamat, Karthik C.", "team_strengths": "A highly cohesive team that has been working together for over 8 years. They possess a blend of data science, engineering, and product experience from major tech companies like Bosch and IBM. The team holds 10 combined patents, indicating strong technical and innovative capabilities." }, "traction_and_gtm": { "booked_customers": [ "Bosch", "Abha Private Hospital (KSA)", "IDBI Bank", "Al Borg Diagnostics", "Rice University" ], "pilots_running": [ "Mercedes-Benz", "Infoline", "SEG Automotive" ], "engagement_pipeline": "Vetrina, Saudi Telecom, Sobha group, Accolade, HDFCergo, Pfizer, Maruti Suzuki, & Tata Elxsi.", "recognitions": "Winner of E-LEVATE 2023, Incubated at IIMB NSRCEL, and selected for Microsoft for Startups.", "gtm_strategy": "A partnership-led model focusing on warm introductions from data companies. This is supported by a multi-channel marketing strategy including webinars, community building, strategic SEO, thought leadership, and hosting on cloud marketplaces." }, "business_model": { "ideal_customer_profile": "Medium to large enterprises with 500+ employees and $5M+ in revenue.", "revenue_streams": [ "Per subscription per month billing", "One-time fee for on-premise deployment", "Annual maintenance and support contracts", "Custom development" ], "key_metrics": { "average_contract_value": "$150k - $300k", "client_lifetime_value": "$1 Million+", "average_sales_cycle": "9 to 12 months" }, "case_study_example": "A contract with Abha Hospitals for 80 subscriptions at $60/user/month plus a $20k setup fee resulted in a Total Contract Value of ~$98,000/year, with the potential to expand to 400 subscriptions." }, "financial_projections": { "fy_25_26_revenue": "$400,000 (projected)", "growth_trajectory": "The company projects revenue of $0.4M in FY 25-26, growing to $1.2M in FY 26-27 and $1.8M in FY 27-28. The projection chart shows aggressive subsequent growth, though the '$360million' label for FY 29-30 is ambiguous and appears disproportionate to the graphed revenue and cost components, requiring clarification." }, "the_ask": { "round_size": "INR 5 Crores", "round_type": "Seed Stage", "use_of_funds": { "sales_and_marketing": "60%", "product_development": "30%", "operational_costs": "10%" }, "exit_strategy": { "short_term": "Series A or B exit with an anticipated 5x return.", "long_term": "Exit via IPO with an anticipated 30x to 40x return." } }, "potential_risks": { "market_competition": "The AI and data analytics space is highly competitive. While Sia's 'Agentic AI' approach is a differentiator, they will compete with established BI players and other well-funded startups.", "sales_cycle": "A 9-12 month sales cycle for enterprise clients is long and capital-intensive. Scaling the sales team and process efficiently will be a key challenge.", "technical_risk": "The solution's effectiveness depends on its ability to seamlessly integrate with a wide variety of legacy and modern data systems, which can be technically complex.", "model_scalability": "The GTM strategy relies on partnerships for warm introductions. The ability to build and scale this partner ecosystem effectively will be critical to achieving revenue goals." } } }

json_to_pdf(data, "investment_memo.pdf")