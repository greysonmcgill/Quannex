# QUAN Recovery - Real World Deployment Roadmap

## Executive Summary

This document outlines the complete requirements for deploying QUAN Recovery as a fully operational debt collection business, including regulatory licensing, technology infrastructure, vendor relationships, and operational framework.

---

## Phase 1: Business Formation & Legal Structure

### 1.1 Entity Formation

| Item | Cost | Timeline | Notes |
|------|------|----------|-------|
| Delaware C-Corp Formation | $500 | 1-2 days | Stripe Atlas or Clerky recommended for investor-friendly structure |
| Registered Agent (DE) | $150/year | Same day | Required for Delaware corps |
| EIN (Federal Tax ID) | Free | 1 day | IRS Form SS-4 |
| State Business Registrations | $50-500/state | 1-2 weeks | Register in states where you operate |
| D&B Number | Free | 1 week | Required for enterprise contracts |

### 1.2 Corporate Documents Needed

- Certificate of Incorporation
- Bylaws
- Board Resolutions
- Stock Purchase Agreements
- IP Assignment Agreements
- Founder Vesting Agreements (4-year, 1-year cliff standard)

### 1.3 Recommended Legal Counsel

| Firm Type | Purpose | Budget |
|-----------|---------|--------|
| Startup Corporate (Cooley, Gunderson, WSGR) | Formation, fundraising | $15-25K initial |
| Regulatory/Compliance Specialist | FDCPA, TCPA, state licensing | $20-50K ongoing |
| Employment Counsel | Hiring, contractor agreements | $5-10K |

---

## Phase 2: Regulatory Licensing

### 2.1 Federal Requirements

| Requirement | Agency | Cost | Timeline |
|-------------|--------|------|----------|
| CFPB Registration | Consumer Financial Protection Bureau | Free | 2 weeks |
| FTC Compliance | Federal Trade Commission | Free | N/A (self-certify) |

### 2.2 State Collection Agency Licenses

**CRITICAL**: You MUST be licensed in each state where debtors reside before contacting them.

| Priority States | License Fee | Bond Required | Timeline |
|-----------------|-------------|---------------|----------|
| California | $300 | $25,000 | 60-90 days |
| Texas | $500 | $10,000 | 30-45 days |
| New York | $1,000 | $5,000 | 90-120 days |
| Florida | $300 | $50,000 | 45-60 days |
| Illinois | $100 | None | 30 days |
| Pennsylvania | $300 | $5,000 | 30-45 days |
| Ohio | $500 | None | 30 days |
| Georgia | $250 | None | 30 days |
| North Carolina | $500 | $15,000 | 45-60 days |
| New Jersey | $300 | $5,000 | 60-90 days |

**Total for Top 10 States**: ~$4,000 fees + ~$115,000 in bonds

### 2.3 Surety Bonds

| Provider | Notes |
|----------|-------|
| SuretyBonds.com | Quick online quotes |
| JW Surety Bonds | Specializes in collection agency bonds |
| Traveler's Insurance | Larger bonds, better rates |

**Typical Cost**: 1-5% of bond amount annually (e.g., $115K bond = $1,150-$5,750/year)

### 2.4 Professional Associations (Recommended)

| Association | Annual Fee | Benefits |
|-------------|------------|----------|
| ACA International | $500-2,000 | Industry credibility, compliance resources, networking |
| RMAI (Receivables Management Association) | $1,000+ | Debt buying certification, best practices |
| DBA International | $500+ | Additional credibility |

---

## Phase 3: Technology Infrastructure

### 3.1 Cloud Infrastructure (AWS Recommended)

| Service | Purpose | Monthly Cost (Starting) |
|---------|---------|------------------------|
| EC2 (t3.xlarge x 3) | Application servers | $400 |
| RDS PostgreSQL (db.r5.large) | Primary database | $300 |
| ElastiCache Redis | Caching, sessions | $150 |
| S3 | Document storage | $50 |
| CloudFront | CDN | $50 |
| Route 53 | DNS | $10 |
| VPC + NAT Gateway | Networking | $100 |
| CloudWatch | Monitoring | $50 |
| WAF | Security | $50 |
| **Total** | | **~$1,200/month** |

**Scale Projection**:
- 10K accounts/month: $1,500/month
- 100K accounts/month: $5,000/month
- 1M accounts/month: $25,000/month

### 3.2 Required SaaS Subscriptions

| Service | Purpose | Monthly Cost |
|---------|---------|--------------|
| **Communications** | | |
| Twilio | SMS, Voice | $0.0075/SMS, $0.013/min voice |
| SendGrid | Email | $90/month (100K emails) |
| Plivo (backup) | Redundant SMS/Voice | Pay-as-go |
| **Payments** | | |
| Stripe | Card processing | 2.9% + $0.30/txn |
| Plaid | Bank verification | $0.30/verification |
| Dwolla | ACH processing | $0.25/ACH |
| **Data & Skip Tracing** | | |
| LexisNexis Accurint | Skip tracing | $0.50-2.00/lookup |
| Experian | Credit data | Enterprise pricing |
| TransUnion | Credit data | Enterprise pricing |
| IDology | Identity verification | $0.15/verification |
| **Compliance** | | |
| ComplianceEase | TCPA/FDCPA rules | $500/month |
| TCPA Defender | Do-not-call scrubbing | $200/month |
| Gryphon Networks | Call recording/compliance | $300/month |
| **Operations** | | |
| Zendesk | Customer support | $150/month |
| Slack | Team communication | $12.50/user/month |
| Google Workspace | Email, docs | $12/user/month |
| GitHub Enterprise | Code repository | $21/user/month |
| Datadog | Application monitoring | $300/month |

### 3.3 Development Tools & Licenses

| Tool | Purpose | Cost |
|------|---------|------|
| JetBrains (PyCharm, etc.) | IDE | $250/user/year |
| Postman | API testing | Free-$12/user/month |
| Figma | Design | $15/user/month |
| Linear | Project management | $8/user/month |

### 3.4 Security & Compliance Tools

| Tool | Purpose | Cost |
|------|---------|------|
| Vanta | SOC 2 compliance automation | $10,000/year |
| Snyk | Security scanning | $500/month |
| 1Password Business | Password management | $8/user/month |
| Okta | SSO/Identity | $5/user/month |

---

## Phase 4: Vendor Relationships

### 4.1 Payment Processing Setup

**Primary: Stripe**
- Apply at stripe.com/connect
- Debt collection = "high-risk" category
- Expect enhanced review (2-4 weeks)
- Provide business plan, compliance documentation
- Reserve requirement: 10-30% of volume initially

**Backup: Square / PayPal**
- Apply concurrently as backup
- Similar enhanced review process

**ACH Processing: Dwolla or Plaid**
- Lower fees than cards (0.5% vs 2.9%)
- Better for payment plans
- Apply: dwolla.com/apply

### 4.2 Communication Providers

**Twilio Setup**
1. Create account at twilio.com
2. Verify business identity
3. Apply for A2P 10DLC registration (required for SMS)
4. Register campaign use case: "Debt Collection"
5. Purchase phone numbers ($1/month each)
6. Timeline: 2-4 weeks for full approval

**SendGrid Setup**
1. Create account at sendgrid.com
2. Verify domain (SPF, DKIM, DMARC)
3. Apply for dedicated IP ($20-80/month)
4. Warm up IP over 30 days

### 4.3 Data Provider Contracts

| Provider | Contact | Typical Minimums |
|----------|---------|------------------|
| LexisNexis Risk Solutions | sales@lexisnexis.com | $500/month minimum |
| Experian | experian.com/business | Enterprise agreement required |
| TransUnion | transunion.com/business | Enterprise agreement required |
| Equifax | equifax.com/business | Enterprise agreement required |

**Timeline**: 4-8 weeks for data provider contracts

### 4.4 Insurance Requirements

| Coverage | Purpose | Annual Premium |
|----------|---------|----------------|
| E&O (Errors & Omissions) | Professional liability | $2,000-5,000 |
| General Liability | Premises, operations | $1,000-2,000 |
| Cyber Liability | Data breach | $3,000-10,000 |
| D&O (Directors & Officers) | Management liability | $2,000-5,000 |
| EPLI (Employment Practices) | HR claims | $1,500-3,000 |

**Recommended Brokers**: Embroker, Vouch, Coalition (startup-focused)

---

## Phase 5: Hardware & Office Setup

### 5.1 Minimal Viable Setup (Remote-First)

| Item | Cost | Notes |
|------|------|-------|
| Laptops (MacBook Pro M3) | $2,500 x 3 | Founder + 2 hires |
| External monitors | $400 x 3 | Productivity |
| Webcams/Mics | $150 x 3 | Video calls |
| Office supplies | $500 | One-time |
| **Total** | **$9,650** | |

### 5.2 WeWork/Coworking (Recommended Initially)

| Option | Monthly Cost | Benefits |
|--------|--------------|----------|
| WeWork Hot Desk | $300/person | Flexibility |
| WeWork Dedicated Desk | $500/person | Consistent space |
| WeWork Private Office | $800-1,500 | Privacy for calls |

### 5.3 Physical Office (Later Stage)

Only needed when:
- Team exceeds 10 people
- Regulatory requirement (some states)
- Enterprise clients require physical presence

---

## Phase 6: Hiring Plan

### 6.1 Critical First Hires

| Role | Timeline | Salary Range | Equity |
|------|----------|--------------|--------|
| CTO / Tech Lead | Month 1-2 | $150-200K | 2-4% |
| VP Compliance | Month 1-2 | $120-160K | 1-2% |
| Senior Engineer | Month 2-3 | $140-180K | 0.5-1% |
| Operations Manager | Month 3-4 | $80-100K | 0.25-0.5% |

### 6.2 Contractor Alternatives (Bootstrap Phase)

| Role | Hourly Rate | Source |
|------|-------------|--------|
| ML Engineer | $100-200/hr | Toptal, Turing |
| Compliance Consultant | $200-400/hr | Industry specialists |
| DevOps | $80-150/hr | Toptal |
| Legal (fractional) | $300-500/hr | Legal firms |

---

## Phase 7: Launch Checklist

### 7.1 Pre-Launch (Weeks 1-8)

- [ ] Form Delaware C-Corp
- [ ] Open business bank account (Mercury, SVB, or Brex)
- [ ] Apply for state licenses (priority states)
- [ ] Obtain surety bonds
- [ ] Set up AWS infrastructure
- [ ] Configure Twilio (A2P 10DLC registration)
- [ ] Configure SendGrid (domain verification)
- [ ] Apply for Stripe Connect
- [ ] Contract with skip trace provider
- [ ] Obtain E&O and Cyber insurance
- [ ] Implement compliance documentation
- [ ] Build MVP collection platform

### 7.2 Soft Launch (Weeks 9-12)

- [ ] First pilot client (1,000 accounts)
- [ ] Validate recovery rates
- [ ] Compliance audit (internal)
- [ ] Iterate on contact sequences
- [ ] Document standard operating procedures
- [ ] Refine cost accounting

### 7.3 Scale Launch (Weeks 13-24)

- [ ] Expand to 10+ clients
- [ ] Hire VP Sales
- [ ] Obtain remaining state licenses
- [ ] Implement SOC 2 compliance
- [ ] Establish credit bureau reporting
- [ ] Build client dashboard

---

## Phase 8: Budget Summary

### 8.1 Minimum Viable Launch Budget

| Category | One-Time | Monthly |
|----------|----------|---------|
| Legal (formation, initial) | $20,000 | - |
| Licensing (10 states) | $4,000 | - |
| Surety Bonds | $5,000 | - |
| Insurance | - | $1,000 |
| Cloud Infrastructure | - | $1,500 |
| SaaS Subscriptions | - | $2,500 |
| Equipment | $10,000 | - |
| Working Capital | $50,000 | - |
| **Total** | **$89,000** | **$5,000** |

### 8.2 Recommended Seed Budget

| Category | Amount |
|----------|--------|
| 18 months runway | $900,000 |
| Salaries (3 FTE) | $600,000 |
| Infrastructure & tools | $100,000 |
| Licensing & compliance | $50,000 |
| Legal & accounting | $75,000 |
| Marketing & sales | $50,000 |
| Contingency (20%) | $175,000 |
| **Total Seed Round** | **$2,000,000** |

---

## Phase 9: Key Milestones

| Milestone | Target | Metric |
|-----------|--------|--------|
| MVP Launch | Month 3 | Platform operational |
| First Client | Month 4 | 1,000+ accounts |
| Pilot Validation | Month 6 | 35%+ recovery demonstrated |
| $100K MRR | Month 9 | 10+ clients |
| SOC 2 Type 1 | Month 12 | Enterprise-ready |
| $1M ARR | Month 15 | 50+ clients |
| Series A | Month 18 | $15M raise |

---

## Phase 10: Regulatory Compliance Framework

### 10.1 FDCPA Requirements

- Validation notice within 5 days of initial contact
- Cease communication on written request
- No harassment, oppression, or abuse
- No false or misleading representations
- Proper debt validation procedures

### 10.2 TCPA Requirements

- Prior express consent for autodialed calls/texts
- Honor do-not-call requests
- Calling hours: 8am-9pm local time
- Caller ID requirements

### 10.3 Regulation F Requirements (CFPB)

- 7-in-7 rule: Max 7 calls per week per debt
- Limited-content messages allowed
- Email/text with proper disclosures
- Model validation notice provided

### 10.4 State-Specific Requirements

Each state has unique requirements. Priority items:
- California: Stricter mini-FDCPA, privacy laws
- New York: Separate licensing, strict enforcement
- Texas: Surety bond requirements
- Massachusetts: Wage assignment restrictions

---

## Appendix A: Vendor Contact List

### Cloud & Infrastructure
- AWS: aws.amazon.com/contact-us
- Google Cloud: cloud.google.com/contact
- Azure: azure.microsoft.com/contact

### Communications
- Twilio: twilio.com/help/sales
- SendGrid: sendgrid.com/contact
- Plivo: plivo.com/contact

### Payments
- Stripe: stripe.com/contact/sales
- Plaid: plaid.com/contact
- Dwolla: dwolla.com/contact

### Data Providers
- LexisNexis: risk.lexisnexis.com/contact-us
- Experian: experian.com/business/contact
- TransUnion: transunion.com/contact

### Compliance
- ACA International: acainternational.org
- ComplianceEase: complianceease.com
- Gryphon Networks: gryphonnetworks.com

---

## Appendix B: Recommended Reading

1. "Getting Started in the Debt Collection Business" - ACA International
2. CFPB Debt Collection Final Rule (Regulation F)
3. FTC Debt Collection FAQs
4. State-by-state licensing guide (RMAI)
5. TCPA Compliance Handbook

---

*Document Version: 1.0*
*Last Updated: January 2026*
*Prepared for: QUAN Recovery*
