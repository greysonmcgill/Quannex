# QUAN Recovery - Implementation Checklist

## Week 1-2: Foundation

### Business Formation
- [ ] **Day 1-2**: Form Delaware C-Corp
  - Option A: Stripe Atlas ($500) - https://stripe.com/atlas
  - Option B: Clerky ($799) - https://clerky.com
  - Option C: Attorney ($2,000-5,000)

- [ ] **Day 3**: Open Business Bank Account
  - Mercury (recommended for startups): https://mercury.com
  - Brex (if need credit): https://brex.com
  - Silicon Valley Bank (traditional): https://svb.com

- [ ] **Day 4-5**: Set up accounting
  - QuickBooks Online: $30/month
  - Hire fractional CFO/bookkeeper: Pilot.com or Bench.co

### Initial Legal
- [ ] Engage startup counsel (get referrals from accelerators/VCs)
- [ ] Draft founder agreements
- [ ] IP assignment agreements
- [ ] Initial compliance review

---

## Week 3-4: Licensing & Compliance

### State Licensing Applications
Priority order based on BNPL debtor concentration:

| State | Application URL | Fee | Timeline |
|-------|-----------------|-----|----------|
| 1. California | dfpi.ca.gov | $300 | 60-90 days |
| 2. Texas | occc.texas.gov | $500 | 30-45 days |
| 3. Florida | flofr.gov | $300 | 45-60 days |
| 4. New York | dfs.ny.gov | $1,000 | 90-120 days |
| 5. Illinois | idfpr.com | $100 | 30 days |

### Surety Bonds
- [ ] Get quotes from 3 providers:
  - SuretyBonds.com
  - JWSuretyBonds.com
  - BondExchange.com
- [ ] Purchase bonds for licensed states

### Compliance Setup
- [ ] Purchase TCPA compliance software
- [ ] Set up DNC (Do Not Call) scrubbing
- [ ] Create compliance policies and procedures
- [ ] Draft validation notice templates
- [ ] Create call scripts (FDCPA compliant)

---

## Week 5-6: Technology Infrastructure

### Cloud Setup (AWS)

```bash
# Infrastructure as Code - Terraform recommended
# Basic setup commands:

# 1. Create AWS Account
# https://aws.amazon.com/free/

# 2. Install AWS CLI
brew install awscli

# 3. Configure credentials
aws configure

# 4. Create VPC and basic infrastructure
# Use CloudFormation or Terraform
```

### Required AWS Services
- [ ] VPC with public/private subnets
- [ ] EC2 instances (start with t3.large)
- [ ] RDS PostgreSQL (db.t3.medium to start)
- [ ] ElastiCache Redis
- [ ] S3 buckets (documents, backups)
- [ ] CloudWatch (monitoring)
- [ ] IAM roles and policies
- [ ] Secrets Manager
- [ ] Certificate Manager (SSL)

### Domain & DNS
- [ ] Purchase domain: quanrecovery.com (if available)
- [ ] Set up Route 53
- [ ] Configure SSL certificates
- [ ] Set up email (Google Workspace or Microsoft 365)

---

## Week 7-8: Communication Providers

### Twilio Setup (SMS/Voice)

```python
# 1. Create account: twilio.com/try-twilio
# 2. Verify business identity
# 3. A2P 10DLC Registration (REQUIRED for SMS)

# Twilio A2P Registration Steps:
# a) Register your brand (company info)
# b) Register campaign (use case: "Debt Collection")
# c) Wait for approval (2-4 weeks)
# d) Purchase phone numbers

# Example Twilio setup code:
from twilio.rest import Client

account_sid = 'your_account_sid'
auth_token = 'your_auth_token'
client = Client(account_sid, auth_token)

# Send SMS
message = client.messages.create(
    body="This is an attempt to collect a debt...",
    from_='+1234567890',
    to='+0987654321'
)
```

### SendGrid Setup (Email)

```python
# 1. Create account: sendgrid.com
# 2. Verify domain (add DNS records)
# 3. Create API key
# 4. Request dedicated IP for deliverability

# DNS Records needed:
# - SPF record
# - DKIM record
# - DMARC record

# Example SendGrid code:
import sendgrid
from sendgrid.helpers.mail import Mail

sg = sendgrid.SendGridAPIClient(api_key='your_api_key')

message = Mail(
    from_email='collections@quanrecovery.com',
    to_emails='debtor@example.com',
    subject='Important Notice Regarding Your Account',
    html_content='<p>This is an attempt to collect a debt...</p>'
)

response = sg.send(message)
```

---

## Week 9-10: Payment Processing

### Stripe Setup

1. **Apply for Stripe Account**
   - Go to: stripe.com/connect
   - Select: Platform or Marketplace
   - Industry: Financial Services > Debt Collection

2. **Enhanced Review**
   - Prepare business plan
   - Compliance documentation
   - Licensing proof
   - Expected volume projections
   - Timeline: 2-4 weeks for approval

3. **Integration**
```python
import stripe
stripe.api_key = "sk_live_..."

# Create payment intent
intent = stripe.PaymentIntent.create(
    amount=15000,  # $150.00 in cents
    currency='usd',
    payment_method_types=['card'],
    metadata={
        'account_id': 'ACC123',
        'debtor_id': 'DBT456'
    }
)
```

### ACH Setup (Plaid + Dwolla)

```python
# Plaid - Bank account verification
from plaid import Client

client = Client(
    client_id='your_client_id',
    secret='your_secret',
    environment='production'
)

# Dwolla - ACH transfers
import dwollav2
client = dwollav2.Client(
    key='your_key',
    secret='your_secret',
    environment='production'
)
```

---

## Week 11-12: Data Provider Integration

### LexisNexis Accurint

1. **Contact Sales**: risk.lexisnexis.com/contact-us
2. **Required Documentation**:
   - Business license
   - Collection agency licenses
   - Permissible purpose certification
   - GLBA compliance attestation

3. **Integration**: REST API available
4. **Pricing**: ~$0.50-2.00 per lookup
5. **Timeline**: 4-6 weeks for approval

### Credit Bureau Access

For credit reporting (not just pulling):
- Join a credit bureau service bureau
- Options: e-OSCAR, Metro 2 format
- Timeline: 3-6 months for direct reporting

---

## Week 13-16: MVP Development

### Core Features Checklist

- [ ] **Account Management**
  - Import accounts (CSV, API)
  - Account scoring
  - Segmentation
  - Status tracking

- [ ] **Contact Engine**
  - SMS campaigns
  - Email campaigns
  - Contact scheduling
  - DNC compliance

- [ ] **Payment Processing**
  - One-click payment links
  - Payment plans
  - ACH processing
  - Receipt generation

- [ ] **Compliance**
  - Validation notices
  - Call recording
  - Audit logging
  - Consent tracking

- [ ] **Reporting**
  - Recovery metrics
  - Client reports
  - Agent performance
  - Financial reporting

---

## Week 17-20: Pilot Launch

### Client Acquisition

1. **Target First Clients**:
   - Tier 2/3 BNPL providers
   - Regional banks
   - Credit unions
   - Fintech startups

2. **Pilot Structure**:
   - 1,000-5,000 accounts
   - 90-day pilot period
   - Success-based pricing (30% contingency)
   - No upfront fees

3. **Outreach Channels**:
   - LinkedIn direct outreach
   - Industry conferences (Collections & Credit Risk)
   - ACA International networking
   - Warm introductions

### Pilot Metrics to Track

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recovery Rate | 35%+ | Collected / Total Balance |
| Contact Rate | 70%+ | Reached / Total Accounts |
| Response Rate | 25%+ | Responded / Contacted |
| Payment Conversion | 15%+ | Paid / Responded |
| Cost per Dollar | <$0.25 | Total Cost / Collected |
| Compliance Issues | 0 | Violations / Total Contacts |

---

## Ongoing: Compliance Calendar

### Daily
- [ ] Review DNC requests
- [ ] Check complaint queue
- [ ] Monitor call recordings (sample)

### Weekly
- [ ] Compliance metrics review
- [ ] License renewal tracking
- [ ] Vendor SLA review

### Monthly
- [ ] CFPB complaint analysis
- [ ] State regulatory updates
- [ ] Staff compliance training

### Quarterly
- [ ] Internal compliance audit
- [ ] Policy review/updates
- [ ] Insurance review

### Annually
- [ ] State license renewals
- [ ] Bond renewals
- [ ] External compliance audit
- [ ] SOC 2 audit (once applicable)

---

## Budget Tracker

### One-Time Costs

| Item | Budgeted | Actual | Status |
|------|----------|--------|--------|
| C-Corp Formation | $500 | | [ ] |
| Initial Legal | $20,000 | | [ ] |
| State Licenses (10) | $4,000 | | [ ] |
| Surety Bonds | $5,000 | | [ ] |
| Equipment | $10,000 | | [ ] |
| **Total One-Time** | **$39,500** | | |

### Monthly Recurring

| Item | Budgeted | Actual | Status |
|------|----------|--------|--------|
| AWS Infrastructure | $1,500 | | [ ] |
| Twilio (est.) | $500 | | [ ] |
| SendGrid | $100 | | [ ] |
| SaaS Tools | $500 | | [ ] |
| Insurance | $1,000 | | [ ] |
| Compliance Tools | $500 | | [ ] |
| Coworking | $500 | | [ ] |
| **Total Monthly** | **$4,600** | | |

---

## Key Contacts Template

### Legal
- Corporate Counsel: ________________
- Compliance Counsel: ________________
- Employment Counsel: ________________

### Vendors
- AWS Account Manager: ________________
- Twilio Support: ________________
- Stripe Account Manager: ________________
- LexisNexis Rep: ________________

### Insurance
- Broker: ________________
- Policy Numbers: ________________

### Banking
- Primary Bank: ________________
- Account Numbers: ________________

---

## Emergency Procedures

### Compliance Emergency
1. Stop all outbound communications immediately
2. Contact compliance counsel
3. Document incident thoroughly
4. File incident report
5. Remediate and resume

### Data Breach
1. Activate incident response plan
2. Contact cyber insurance carrier
3. Engage forensics firm
4. Notify affected parties (per state laws)
5. File regulatory notifications

### Service Outage
1. Activate backup systems
2. Notify clients
3. Escalate with vendor
4. Document for SLA claims

---

*Last Updated: January 2026*
