# Drug Knowledge Graph Model

## Nodes

| Node Type | Description |
|-----------|-------------|
| `Drug` | Pharmaceutical product |
| `ROA` | Route of Administration |
| `ActiveIngredient` | Therapeutic component of a drug |
| `Excipient` | Non-active component of a drug |
| `GenericGroup` | Group of equivalent drugs |
| `LegalSubstanceList` | Regulatory classification |
| `Indication` | Medical condition a drug treats |
| `Contraindication` | Medical condition where a drug should not be used |

## Node Properties

### 1. Drug
- `id`: Unique identifier
- `name`: Drug name
- `theriaque_id`: External reference ID
- `pharmacokinetics`: How the drug moves through the body
- `single_dose_unit`: Amount in a single dose
- `doses_per_package`: Number of doses in package
- `type_of_packaging`: Physical packaging format
- `retail_price`: Commercial price
- `retail_reimbursement_rate`: Insurance coverage percentage
- `dispensing_modalities`: How the drug can be dispensed
- `conservation`: Storage requirements
- `posologies`: Dosage information
- `drug_interactions`: Interactions with other drugs
- `pregnancy`: Safety during pregnancy
- `breastfeeding`: Safety during breastfeeding
- `female_fertility`: Impact on fertility

### 2. ROA
- `id`: Unique identifier
- `name`: Name of administration route
- `theriaque_id`: External reference ID

### 3. ActiveIngredient
- `id`: Unique identifier
- `name`: Ingredient name
- `strength`: Dosage strength
- `theriaque_id`: External reference ID

### 4. Excipient
- `id`: Unique identifier
- `name`: Excipient name
- `theriaque_id`: External reference ID

### 5. GenericGroup
- `id`: Unique identifier
- `name`: Group name
- `theriaque_id`: External reference ID

### 6. LegalSubstanceList
- `id`: Unique identifier
- `name`: List name
- `theriaque_id`: External reference ID

### 7. Indication
- `id`: Unique identifier
- `name`: Indication name
- `details`: Additional information
- `theriaque_id`: External reference ID

### 8. Contraindication
- `id`: Unique identifier
- `type`: Type of contraindication
- `theriaque_id`: External reference ID

## Relationships (Edges)

### 1. IsAdministeredVia
- **From**: `Drug`
- **To**: `ROA`
- **Properties**: None

### 2. ContainsActiveIngredient
- **From**: `Drug`
- **To**: `ActiveIngredient`
- **Properties**: None

### 3. ContainsExcipient
- **From**: `Drug`
- **To**: `Excipient`
- **Properties**: None

### 4. IsPartOfGenericGroup
- **From**: `Drug`
- **To**: `GenericGroup`
- **Properties**: None

### 5. IsReferenceDrugInGroup
- **From**: `Drug`
- **To**: `GenericGroup`
- **Properties**:
  - `relation_type`: Type of relationship (REFERENCE)

### 6. IsGenericDrugInGroup
- **From**: `Drug`
- **To**: `GenericGroup`
- **Properties**:
  - `relation_type`: Type of relationship (GENERIC)

### 7. BelongsToLegalSubstanceList
- **From**: `Drug`
- **To**: `LegalSubstanceList`
- **Properties**: None

### 8. HasIndication
- **From**: `Drug`
- **To**: `Indication`
- **Properties**: None

### 9. HasContraindication
- **From**: `Drug`
- **To**: `Contraindication`
- **Properties**:
  - `level`: Severity of contraindication (e.g., CONTRE-INDICATION ABSOLUE)
  - `subtypes`: Specific forms of contraindication
  - `comment`: Additional information

## Visualization

```
                        ┌──────────────┐
                        │ LegalSubstanceList │
                        └────────┬─────┘
                               ▲
                               │ BelongsToLegalSubstanceList
                               │
┌──────────────┐      ┌────────┴─────┐      ┌───────────────┐
│ ActiveIngredient │◄─────┤    Drug    ├─────►│    ROA     │
└──────┬─────────┘      └─────┬───────┘      └───────────────┘
       ▲                     ▲│▲
       │                    / │ \
       │ ContainsActiveIngredient     │ IsAdministeredVia
       │                  /   │   \
┌──────┴─────────┐      /    │    \      ┌───────────────┐
│   Excipient    │◄────┘     │     └─────►│  Indication  │
└────────────────┘           │            └───────────────┘
       ▲                     │
       │                     │ HasContraindication
       │ ContainsExcipient   │
       │                     ▼
┌──────┴─────────┐     ┌─────────────────┐
│  GenericGroup  │     │ Contraindication │
└────────────────┘     └─────────────────┘
       ▲
       │ IsPartOfGenericGroup/IsReferenceDrugInGroup/IsGenericDrugInGroup
       │
       └─────────────────────
```
