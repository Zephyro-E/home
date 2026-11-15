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

## Calendario (Fase 4, implementado en `apps/events/models.py`)

```
Event                (HouseholdOwnedModel)
  title, kind ('general'|'appointment'|'birthday'|'celebration'|'trip'),
  description, location, all_day,
  starts_at/ends_at (UTC, si tiene hora)  ó  start_date/end_date (date, día completo),
  recurrence_rule (RRULE sin DTSTART, p. ej. "FREQ=WEEKLY;INTERVAL=2;UNTIL=20270301T235959"),
  participants → User (muchos a muchos; miembros del hogar; en privados solo el dueño)

Task (ampliado)      recurrence_rule, recurrence_spawned (ya se creó la siguiente)
```

Las tareas con `due_date` se proyectan en el calendario al consultar, sin copiarse.

## Películas, series y sitios (Fase 5, `apps/media` y `apps/places`)

```
Title                (HouseholdOwnedModel) title, kind ('movie'|'series'), year?, genre,
                     platform, synopsis, image_url, url,
                     status ('pending'|'watching'|'watched'|'dropped')
TitleRating          title, user, stars 1–5   (único por persona)
TitleComment         title, author, body
SeriesProgress       title, user, season, episode   (único por persona)

Place                (HouseholdOwnedModel) name, category, location, description, url,
                     image_url, status ('pending'|'visited'), visited_on?
PlaceRating          place, user, stars 1–5   (único por persona)
PlaceComment         place, author, body
```

Valoraciones y comentarios heredan de `AbstractRating` / `AbstractComment` (`apps/core/social.py`).

## Finanzas I (Fase 6, implementado en `apps/finance/models.py`)

```
Account              (HouseholdOwnedModel) name, kind ('bank'|'cash'|'card'|'savings'),
                     initial_balance_cents (puede ser negativo), is_archived
Category             (HouseholdOwnedModel, siempre shared) name, kind ('expense'|'income'),
                     color   (único por hogar + tipo + nombre)
Transaction          (HouseholdOwnedModel) kind ('expense'|'income'|'transfer'),
                     amount_cents (> 0), date, account → Account (PROTECT),
                     to_account → Account? (solo transferencias), category → Category?
                     (SET_NULL; no en transferencias), description, notes
                     visibility calculada: shared si toca alguna cuenta común (ADR-019)
```

## Finanzas II (Fase 7)

```
Transaction (ampliado) is_split   (gasto compartido; quien paga = dueño de la cuenta)
TransactionSplit     transaction, user, share_bp (10 000 = 100 %), amount_cents
                     (las partes suman exactamente el importe)
Settlement           (HouseholdOwnedModel, siempre shared) from_user, to_user,
                     amount_cents, date, note        (pago entre miembros)
Budget               (HouseholdOwnedModel, siempre shared) category (1 a 1, de gastos),
                     amount_cents mensual
SavingsGoal          (HouseholdOwnedModel) name, target_cents, account?, saved_cents,
                     target_date?
Membership.default_share_bp   reparto por defecto (se normaliza para sumar 100 %)
```

Saldo de una persona = lo que adelantó en gastos compartidos − su parte de todos ellos + pagos hechos − pagos recibidos.

## Fase 9

```
PasswordReset        user, household, token_hash (solo el hash), created_by, expires_at (24 h),
                     used_at        (enlace de un solo uso para elegir contraseña, ADR-023)
Notification         (HouseholdOwnedModel, siempre private; owner = quien recibe)
                     kind, actor, title, url, read_at
```

## Módulos posteriores (esbozo)

- **Recetas (F8)**: `Recipe`, `RecipeIngredient` (cantidad, unidad, nombre), etiquetas, valoraciones; acción "añadir a la lista de la compra" → `GroceryItem`.

## Diagrama de relaciones del núcleo

```
User ──< Membership >── Household ──< Invitation
  │                        │
  └──< (owner) ── elementos de módulos ──┘ (household)
```
