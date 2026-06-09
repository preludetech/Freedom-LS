# Vultr vs AWS vs GCP in South Africa: a cost-honest comparison

**Vultr Johannesburg remains the clear winner for a bootstrapped B2B SaaS at $100–140/month for a production-ready stack, roughly 3× cheaper than an equivalent AWS setup and 2× cheaper than GCP.** The hyperscaler premium in South African regions is not just about higher base prices — it compounds through egress fees, NAT gateways, load balancers, and public IPv4 charges that don't exist on Vultr. This report pins down every dollar across all three providers so FreedomLS can make infrastructure decisions backed by real numbers, not vibes.

AWS launched af-south-1 (Cape Town) in April 2020 with 3 AZs and roughly 220 services. GCP opened africa-south1 (Johannesburg) in early 2024 with 3 zones. Vultr has operated in Johannesburg since late 2022 with uniform global pricing. All three keep data in South Africa for POPIA compliance, but the cost structures diverge dramatically at bootstrapped scale.

---

## Compute pricing reveals a 2–4× gap

The target spec is **4 vCPU / 8 GB RAM**. Vultr offers this exact configuration. AWS and GCP bundle 4 vCPU with 16 GB RAM in their standard tiers, so we compare the closest equivalents.

| Provider | Instance type | vCPU | RAM | Storage | Monthly (on-demand) | With 1Y commitment |
|---|---|---|---|---|---|---|
| **Vultr** | Regular Performance | 4 | 8 GB | 160 GB SSD | **$40** | N/A |
| **Vultr** | High Performance (NVMe) | 4 | 8 GB | 180 GB NVMe | **$48** | N/A |
| **GCP** | e2-custom (4 vCPU, 8 GB) | 4 | 8 GB | — (separate) | **~$89** | ~$56 (1Y CUD) |
| **GCP** | e2-standard-4 | 4 | 16 GB | — (separate) | **$107.62** | $67.80 (1Y CUD) |
| **AWS** | t3.xlarge | 4 | 16 GB | — (separate) | **~$152** | ~$95 (1Y RI) |
| **AWS** | t4g.xlarge (ARM) | 4 | 16 GB | — (separate) | **~$123** | ~$77 (1Y RI) |

GCP's custom machine types give it an edge over AWS here — you can configure exactly 4 vCPU / 8 GB without paying for unused RAM. GCP's **~10% regional surcharge** over us-central1 is also gentler than AWS's **~25% premium** over us-east-1.

For a more apples-to-apples comparison at 2 vCPU / 8 GB (sufficient for early-stage FreedomLS):

| Provider | Instance | Monthly |
|---|---|---|
| Vultr High Performance | 2 vCPU / 4 GB | **$24** |
| GCP e2-standard-2 | 2 vCPU / 8 GB | **$53.81** |
| AWS t3.large | 2 vCPU / 8 GB | **~$76** |
| AWS t4g.large (ARM) | 2 vCPU / 8 GB | **~$61** |

Vultr's pricing includes storage and **4–6 TB of bandwidth**. AWS and GCP charge separately for both — a critical distinction that inflates their real cost beyond the headline compute number. A 100 GB gp3 EBS volume on AWS adds ~$9.60/month in af-south-1; 100 GB of pd-balanced on GCP adds ~$10.98/month.

---

## Managed PostgreSQL: where the gap widens

Managed databases are where hyperscalers extract significant margin. For a B2B SaaS handling course data, user records, and assessment results, a 2 vCPU / 4 GB PostgreSQL instance is the right starting point.

| Provider | Config | Single instance | High availability |
|---|---|---|---|
| **Vultr** Managed DB | 2 vCPU / 4 GB | **~$60/mo** | ~$120 (add replica) |
| **GCP** Cloud SQL | db-custom-2-4096 | **~$89/mo** | ~$178/mo (HA doubles compute) |
| **AWS** RDS | db.t3.medium (2 vCPU, 4 GB) | **~$62/mo** | ~$124/mo (Multi-AZ) |
| **AWS** RDS | db.t4g.medium (ARM) | **~$50/mo** | ~$100/mo |

AWS RDS pricing for the smallest tier actually competes with Vultr on the headline number — **~$62/month for db.t3.medium** in af-south-1 is surprisingly close to Vultr's ~$60. The catch is that RDS adds storage costs ($0.138/GB/month for gp3), and the t3 instances are burstable with CPU credit limitations. GCP Cloud SQL is the most expensive option at ~$89/month for the equivalent tier because it charges per-vCPU and per-GB-memory at higher component rates.

All three include automated backups. Vultr offers **14-day point-in-time recovery** with WAL-based PITR. AWS includes backup storage equal to your database size for free. GCP charges $0.105/GB/month for all backup storage.

For the step-up tier (2 vCPU / 8 GB):

| Provider | Config | Single instance |
|---|---|---|
| Vultr | 4 vCPU / 8 GB (next tier up) | ~$120/mo |
| GCP Cloud SQL | db-custom-2-8192 | ~$111/mo |
| AWS RDS | db.t3.large | ~$124/mo |

---

## Data egress is the hidden cost killer

This is where the comparison shifts decisively. A B2B LMS serving course content, PDFs, and potentially video will generate meaningful egress. Here is what each provider charges per GB of outbound data to the internet:

| Egress tier | Vultr | GCP (Standard tier) | GCP (Premium tier) | AWS af-south-1 |
|---|---|---|---|---|
| First free | Included (4–6 TB) | 200 GB | 1 GB | 100 GB |
| Per GB after free | **$0.01** | $0.085 | $0.12–$0.19 | **$0.154** |
| 500 GB egress cost | **$0** (included) | ~$25.50 | ~$60 | ~$61.60 |
| 2 TB egress cost | **$0** (included) | ~$153 | ~$240 | ~$293 |

Vultr includes **4 TB of egress on the $40/month plan and 6 TB on the $48/month plan**, plus a pooled 2 TB account-level free allowance. Overages cost just $0.01/GB. AWS af-south-1 charges **$0.154/GB** — that's **15.4× Vultr's overage rate**. At 2 TB of monthly egress, AWS would charge ~$293 in transfer fees alone, more than the entire Vultr stack.

GCP offers a Standard network tier at $0.085/GB with 200 GB free, which is cheaper than AWS but still 8.5× Vultr's overage rate. The Premium tier (default) charges $0.12–$0.19/GB depending on destination, with South African/African destinations at the higher end.

---

## Object storage and the Cloudflare R2 wildcard

For storing course materials, media uploads, and static assets:

| Provider | Storage/GB/mo | Egress/GB | Free tier | S3 compatible |
|---|---|---|---|---|
| **Cloudflare R2** | $0.015 | **$0.00** | 10 GB + 10M reads | ✅ |
| **Vultr Object Storage** | $18/mo flat (1 TB incl.) | $0.01 | — | ✅ |
| **GCP Cloud Storage** (africa-south1) | ~$0.023 | $0.085–$0.19 | 5 GB (US only) | ✅ (via interop) |
| **AWS S3** (af-south-1) | ~$0.033 | $0.154 | 5 GB (12 months) | ✅ (native) |

**Cloudflare R2 is the standout choice regardless of compute provider.** Zero egress fees, $0.015/GB storage, and a generous free tier make it ideal for an LMS serving downloadable content. For 100 GB of storage with 500 GB of monthly downloads, R2 costs ~$1.50/month. The same workload on S3 in af-south-1 would cost ~$80 (dominated by $77 in egress). R2 works with any compute provider via its S3-compatible API.

One caveat for Vultr Object Storage: it may **not be available in Johannesburg** specifically. Vultr operates object storage "hubs" in only 13 of 32 regions. If Johannesburg isn't one of them, the storage would be served from a hub in Europe or elsewhere, adding latency. R2 sidesteps this entirely with its global edge network.

---

## Total monthly cost: the full picture

These tables include all the costs that actually appear on your bill — not just compute and database, but the ancillary charges that hyperscalers layer on.

### Lean stack: single server with self-managed PostgreSQL

This is the "just ship it" configuration — Django 6 and PostgreSQL on the same box.

| Line item | Vultr JNB | GCP africa-south1 | AWS af-south-1 |
|---|---|---|---|
| Compute (4c/8GB) | $48 (HP NVMe) | ~$89 (e2-custom-4-8192) | ~$152 (t3.xlarge) |
| Boot disk (included vs separate) | Included (180 GB) | ~$11 (100 GB pd-balanced) | ~$10 (100 GB gp3) |
| Public IPv4 | Included | $3.65 | $3.75 |
| Firewall | Free | Free (VPC rules) | Free (Security Groups) |
| DNS | Free | $0.20/zone + $0.40/M queries | $0.50/zone + $0.40/M queries |
| Backups (server snapshots) | $9.60 (20% of plan) | ~$5 (50 GB snapshot) | ~$5 (50 GB EBS snapshot) |
| Egress (50 GB/mo) | Included | ~$4.25 (Std tier) | ~$0 (within 100 GB free) |
| **Monthly total** | **~$58** | **~$113** | **~$171** |

### Comfort stack: managed database + object storage

The production-ready configuration with a managed PostgreSQL instance and object storage for media.

| Line item | Vultr JNB | GCP africa-south1 | AWS af-south-1 |
|---|---|---|---|
| Compute (4c/8GB equiv.) | $48 | ~$89 | ~$152 |
| Boot disk | Included | ~$11 | ~$10 |
| Managed PostgreSQL (2c/4GB) | $60 | ~$89 | ~$62 |
| DB storage (50 GB) | Included | ~$11 | ~$7 |
| Object storage (100 GB) | — (use R2: $1.50) | — (use R2: $1.50) | — (use R2: $1.50) |
| Load balancer | $10 | $18.25 | ~$30 |
| Public IPv4 | Included | $3.65 | $3.75 |
| NAT Gateway | N/A | ~$3.21 + data | ~$39 + data |
| Egress (100 GB/mo) | Included | ~$0 (200 GB Std free) | ~$0 (100 GB free) |
| Server backups | $9.60 | ~$5 | ~$5 |
| DNS | Free | ~$1 | ~$1 |
| **Monthly total** | **~$129** | **~$232** | **~$311** |

### Comfort stack with 1-year commitments

| | Vultr JNB | GCP (1Y CUD) | AWS (1Y RI, no upfront) |
|---|---|---|---|
| **Monthly total** | **~$129** | **~$185** | **~$252** |

AWS's **NAT Gateway** is the single most punishing hidden cost — **~$39/month just sitting idle**, plus $0.054/GB of data processed. It's required if your instances sit in private subnets (which is best practice). You can avoid it by putting EC2 in a public subnet, but that's a security trade-off. GCP's Cloud NAT is far cheaper at ~$3.21/month base.

---

## Compliance is closer than you'd expect

Vultr's compliance posture has improved dramatically and now covers what most B2B SaaS applications need.

| Certification | AWS | GCP | Vultr |
|---|---|---|---|
| ISO 27001 | ✅ | ✅ | ✅ |
| ISO 27017/27018 | ✅ | ✅ | ✅ |
| SOC 2 Type II | ✅ | ✅ | ✅ |
| HIPAA (BAA available) | ✅ | ✅ | ✅ |
| PCI DSS Level 1 SP | ✅ | ✅ | ⚠️ Merchant only (SP coming) |
| FedRAMP | ✅ | ✅ | ❌ (roadmap) |
| POPIA support | ✅ (explicit) | ✅ | ✅ (data in SA) |

For FreedomLS as a B2B LMS, **Vultr's ISO 27001 + SOC 2 Type II covers the vast majority of enterprise procurement requirements**. The gap only matters if you're selling to financial institutions requiring PCI DSS Service Provider certification, government agencies needing FedRAMP-equivalent, or global enterprises with specific hyperscaler mandates in their vendor policies. POPIA compliance is achievable on all three providers since all store data within South Africa.

---

## Automation tooling follows the maturity curve

AWS and GCP have Terraform providers with 1,000+ and 500+ resource types respectively — reflecting decades of service accumulation. Vultr's provider covers ~25 resource types, which maps to Vultr's focused service catalog.

For a Django + PostgreSQL SaaS, Vultr's Terraform provider covers everything needed: instances, managed databases, VPC, firewalls, DNS, load balancers, block storage, and Kubernetes clusters. The `vultr/vultr` provider has **5.3 million downloads** and is actively maintained by Vultr's own team. The `vultr-cli` handles day-to-day operations. The REST API (v2) is well-documented and comprehensive for Vultr's service scope.

The practical difference: on AWS, you can codify IAM policies, CloudWatch alarms, WAF rules, and 200+ service configurations in Terraform. On Vultr, you codify the 10–15 resources you actually use. For a solo developer, **fewer moving parts is a feature, not a limitation**. You'll spend time writing application code instead of infrastructure code.

---

## South African region quirks worth knowing

**AWS af-south-1** is an opt-in region — you must explicitly enable it in account settings before deploying anything. It offers ~220 of AWS's 389 services, missing roughly 43% of the catalog (primarily newer AI/ML features, some specialized analytics, and latest-gen instance families like M7i/M8g). The 3 AZs provide genuine redundancy within the region, and CloudFront has edge locations in both Cape Town and Johannesburg.

**GCP africa-south1** launched in January 2024, making it the newest of the three. It has 3 zones and supports core services (Compute Engine, GKE, Cloud SQL, Cloud Run, Cloud Storage, BigQuery). ARM-based instances (C4A) are not yet available. The region connects via Google's Equiano subsea cable. GCP's Always Free tier for Compute Engine is **restricted to US regions only** — you cannot get a free e2-micro in africa-south1.

**Vultr Johannesburg** operates as a single data center with no AZ concept. This means no in-region redundancy at the infrastructure level — if the facility goes down, your workload goes down. For FreedomLS at current scale, this is an acceptable trade-off mitigated by automated backups and the ability to redeploy to another Vultr region. At the point where 99.99% uptime becomes contractually required, multi-AZ on a hyperscaler becomes worth the premium.

---

## When the hyperscaler premium becomes worth paying

Vultr serves a bootstrapped SaaS well from **$0 to roughly $2–5 million ARR**. The migration triggers are specific and identifiable:

- **Enterprise compliance mandates** — A government contract requiring FedRAMP-equivalent or a bank requiring PCI DSS Level 1 Service Provider certification. These are non-negotiable and only hyperscalers qualify today.
- **Multi-region requirements** — Expanding beyond South Africa to serve East Africa, West Africa, or global markets. AWS has 34 regions; Vultr has 32 but with shallower service depth per region.
- **Auto-scaling under variable load** — If FreedomLS starts handling unpredictable exam-day traffic spikes across thousands of concurrent learners, AWS Auto Scaling Groups or GCP Managed Instance Groups handle this natively. On Vultr, you'd need to build this with Kubernetes (VKE) or custom scripting.
- **Managed AI/ML services** — If FreedomLS adds AI-powered features (adaptive learning, content generation, automated grading), SageMaker or Vertex AI save months of infrastructure work compared to self-hosting models.
- **Team growth past 5–10 engineers** — Hyperscaler IAM, organizational policies, and service catalogs become valuable when multiple developers need controlled access to infrastructure.

The portable architecture strategy is straightforward: Django runs anywhere, PostgreSQL is managed on all three, and S3-compatible storage (especially R2) is provider-agnostic. **A well-structured Vultr deployment can migrate to AWS or GCP in under a week** when the business justifies it.

## Conclusion

The $129/month Vultr comfort stack delivers **equivalent capability** to what costs $232–311/month on GCP or AWS — a **2–3× premium** that buys redundancy and breadth of services a bootstrapped solo-developer SaaS doesn't yet need. The pricing gap is driven less by compute (where GCP is only ~1.8× Vultr) and more by the compounding effect of egress fees, NAT gateways, load balancers, and per-service charges that hyperscalers layer onto every deployment.

Three decisions crystallize from the data. First, **pair Vultr compute with Cloudflare R2** for object storage — R2's zero egress eliminates the single largest variable cost for a content-heavy LMS. Second, **don't assume you'll need multi-AZ redundancy** at launch; Vultr's single-DC model with automated backups and PITR provides sufficient resilience for early B2B customers. Third, **treat the hyperscaler migration as a milestone, not a starting position** — when annual revenue crosses $2M or a contract demands FedRAMP, you'll have the budget and the business case to justify the 3× infrastructure cost. Until then, every dollar saved on hosting is a dollar available for product development.
