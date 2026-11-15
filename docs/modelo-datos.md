# Modelo de datos

> Modelo conceptual. Los nombres de campos son orientativos y se concretan al implementar cada fase.
> Identificadores: UUID. Fechas y horas: UTC (ver ADR-008). Importes: céntimos enteros (ADR-007).

## Núcleo (Fase 1, implementado en `apps/core/models.py`)

```
User                 (modelo propio desde el primer día; inicio de sesión por email)
  id, email (único), name, language ('es'|'en'),
  theme ('system'|'light'|'dark'), password (Argon2id), is_active, is_staff, date_joined
  (avatar: iniciales + color del miembro; foto en la Fase 8, ADR-014)

Household
  id, name, timezone ('Europe/Madrid'), currency ('EUR'), settings (JSON), created_at

Membership           (User ⟷ Household, muchos a muchos)
  household → Household, user → User, role ('admin'|'member'),
  color (color de la persona en la interfaz),
  default_share_bp (reparto por defecto en puntos básicos; 5000 = 50 %), joined_at
  único: (household, user)

Invitation
  id, household → Household, token_hash, role, created_by → User,
  expires_at, used_at?, used_by → User?

File
  id, household → Household, owner → User, file, mime, size, created_at
```

## Patrón común de los módulos

Modelo abstracto `HouseholdOwnedModel`:

```
household   → Household   (obligatorio)
owner       → User        (quien lo creó / su dueño)
visibility  'private' | 'shared'
created_at, updated_at
```

Regla de lectura aplicada por `visible_to(user, household)`:

```
household = hogar activo  AND  user es miembro  AND  (visibility = 'shared' OR owner = user)
```

Escritura: elementos `shared` → cualquier miembro; `private` → solo el dueño.
Pasar un elemento de personal a compartido = cambiar `visibility` (no se copia).

## Compras (Fase 2, implementado en `apps/shopping/models.py`)

```
GroceryItem          (HouseholdOwnedModel, siempre shared; owner = quien lo añadió)
  name, quantity (texto: "2 kg"), is_checked, checked_at?, checked_by?
  (no se duplica: volver a añadir un producto existente lo reactiva)

WishItem             (HouseholdOwnedModel) deseos personales o propuestas comunes
  name, description?, estimated_price_cents?, url?, image_url? (foto subida: Fase 8),
  priority ('low'|'medium'|'high'),
  status ('pending'|'approved'|'bought'|'discarded'), status_changed_by?, status_changed_at?

WishVote             único por (item, user)
  item → WishItem, user, value (+1 | -1), created_at, updated_at
  (solo en elementos shared; retirar voto = borrar fila)

WishComment
  item → WishItem, author, body, created_at, edited_at?
```

## Tareas (Fase 3, implementado en `apps/tasks/models.py`)

```
Task                 (HouseholdOwnedModel)
  title, description?, assignee → User?, status ('todo'|'doing'|'done'),
  position (orden dentro de la columna), due_date (date)?, priority,
  completed_at?, recurrence_rule (RRULE)? (fase 4)

TaskLabel            (HouseholdOwnedModel, siempre shared) name, color (único por hogar + nombre)
Task ⟷ TaskLabel     muchos a muchos
Subtask              task, title, is_done, position
TaskComment          task, author, body, created_at

Reglas: assignee debe ser miembro del hogar; si la tarea es private, solo su dueño.
```

## Módulos posteriores (esbozo)

- **Calendario (F4)**: `Event` (HouseholdOwnedModel: title, description, kind, starts_at/ends_at o start_date/end_date si es de día completo, location, recurrence_rule), `EventParticipant`. Las tareas con `due_date` se proyectan al consultar, sin copiarse.
- **Películas y series (F5)**: `Title` (tipo, género, año, sinopsis, imagen, plataforma, estado), `TitleRating` (por persona), `SeriesProgress` (temporada, episodio).
- **Sitios (F5)**: `Place` (categoría, ubicación, lat/lon opcionales, url, estado, imágenes), `PlaceRating`, `PlaceComment`.
- **Finanzas (F6–F7)**: `Account` (personal o común), `Category`, `Transaction` (tipo ingreso / gasto / transferencia, importe en céntimos, fecha, cuenta, visibilidad), `TransactionSplit` (persona, parte en céntimos), `Budget` (mes, categoría, importe), `SavingsGoal`, `Settlement` (liquidación de saldos entre miembros).
- **Recetas (F8)**: `Recipe`, `RecipeIngredient` (cantidad, unidad, nombre), etiquetas, valoraciones; acción "añadir a la lista de la compra" → `GroceryItem`.

## Diagrama de relaciones del núcleo

```
User ──< Membership >── Household ──< Invitation
  │                        │
  └──< (owner) ── elementos de módulos ──┘ (household)
```
