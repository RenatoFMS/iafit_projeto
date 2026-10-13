# 📄 Contrato de Dados Firestore: Coleção `treinos`

Este documento define a especificação técnica e o contrato de dados entre o motor de Visão Computacional / IA em Python (`core/firebase_client.py`) e a aplicação Front-end (React).

---

## 📌 1. Visão Geral da Coleção

- **Coleção no Firestore:** `treinos`
- **ID do Documento:** Gerado automaticamente pelo Firestore (`db.collection('treinos').document().set(...)`).
- **Momento do Envio:**
  1. Encerramento automático de série por inatividade (**Timeout > 6.0s**).
  2. Mudança de exercício através do menu / atalho de teclado.
  3. Fechamento da aplicação ou clique no botão de saída (`SAIR [ESC]`).

---

## 📋 2. Dicionário de Dados (Campos do Documento)

| Campo | Tipo no Firestore | Tipo no TypeScript | Obrigatório | Descrição | Exemplo |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `exercicio` | `string` | `string` | Sim | Nome oficial do exercício cadastrado no catálogo do IAFit. | `"Agachamento"` |
| `repeticoes` | `number` (integer) | `number` | Sim | Quantidade de repetições concluídas (exercícios dinâmicos) ou tempo em segundos (exercícios isométricos). | `12` |
| `erros_postura` | `number` (integer) | `number` | Sim | Contagem de desvios posturais ou falhas de forma detectadas durante a execução da série. | `0` |
| `calorias` | `number` (double) | `number` | Sim | Estimativa do gasto energético em quilocalorias ($kcal$), calculada com base na duração e no índice MET do exercício. | `3.45` |
| `data` | `Timestamp` | `Timestamp` / `Date` | Sim | Timestamp gerado pelo servidor do Firestore (`firestore.SERVER_TIMESTAMP`) no momento da persistência. | `2026-10-13T19:45:00.000Z` |

---

## 🔍 3. Exemplos Práticos de JSON

### Exemplo 1: Exercício Dinâmico Baseado em Repetições (ex: Agachamento)

```json
{
  "exercicio": "Agachamento",
  "repeticoes": 12,
  "erros_postura": 0,
  "calorias": 3.45,
  "data": {
    "_seconds": 1791935100,
    "_nanoseconds": 450000000
  }
}
```

### Exemplo 2: Exercício Isométrico Baseado em Tempo (ex: Prancha Isométrica)

> **Nota para o Front-end:** Em exercícios isométricos (`Prancha Isométrica`, `Prancha Lateral`, `Agachamento Isométrico`), o campo `repeticoes` armazena os **segundos acumulados sob postura correta**.

```json
{
  "exercicio": "Prancha Isométrica",
  "repeticoes": 45,
  "erros_postura": 1,
  "calorias": 3.28,
  "data": {
    "_seconds": 1791935400,
    "_nanoseconds": 120000000
  }
}
```

---

## ⚛️ 4. Integração no Front-end (React + TypeScript)

### Interface TypeScript (`types/treino.ts`)

```typescript
import { Timestamp } from 'firebase/firestore';

export interface ITreino {
  id?: string;
  exercicio: string;
  repeticoes: number;
  erros_postura: number;
  calorias: number;
  data: Timestamp;
}

/**
 * Interface formatada para renderização direta na UI
 */
export interface ITreinoFormatado {
  id: string;
  exercicio: string;
  quantidade: string; // Ex: "12 reps" ou "45s"
  errosPostura: number;
  caloriasFormatadas: string; // Ex: "3.5 kcal"
  dataHora: string; // Ex: "13/10/2026 19:45"
}
```

### Exemplo de Hook React para Consulta em Tempo Real (`hooks/useTreinos.ts`)

```typescript
import { useState, useEffect } from 'react';
import { collection, query, orderBy, onSnapshot } from 'firebase/firestore';
import { db } from '../services/firebaseConfig';
import { ITreino, ITreinoFormatado } from '../types/treino';

const EXERCICIOS_ISOMETRICOS = [
  'Prancha Isométrica',
  'Prancha Lateral',
  'Agachamento Isométrico'
];

export function useTreinos() {
  const [treinos, setTreinos] = useState<ITreinoFormatado[]>([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    const q = query(collection(db, 'treinos'), orderBy('data', 'desc'));

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const lista: ITreinoFormatado[] = snapshot.docs.map((doc) => {
        const item = doc.data() as ITreino;
        const dataConvertida = item.data?.toDate
          ? item.data.toDate()
          : new Date();

        const ehIsometrico = EXERCICIOS_ISOMETRICOS.includes(item.exercicio);

        return {
          id: doc.id,
          exercicio: item.exercicio,
          quantidade: ehIsometrico ? `${item.repeticoes}s` : `${item.repeticoes} reps`,
          errosPostura: item.erros_postura || 0,
          caloriasFormatadas: `${(item.calorias || 0).toFixed(1)} kcal`,
          dataHora: dataConvertida.toLocaleString('pt-PT', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          })
        };
      });

      setTreinos(lista);
      setCarregando(false);
    });

    return () => unsubscribe();
  }, []);

  return { treinos, carregando };
}
```

---

## 🧮 5. Regras de Negócio e Cálculos

### Fórmula de Gasto Calórico (MET)
As calorias são calculadas e enviadas diretamente pelo Python usando a fórmula padrão de equivalentes metabólicos:

$$\text{Calorias (kcal)} = \left(\frac{\text{tempo\_segundos}}{3600}\right) \times \text{MET} \times \text{peso\_kg}$$

- **`peso_kg` padrão do sistema:** $70.0 \text{ kg}$
- **Precisão:** Arredondado para duas casas decimais no envio.
- **Valores de MET do Catálogo:**
  - *Alta intensidade:* Agachamento ($5.0$), Agachamento Búlgaro ($5.0$), Agachamento Sumô ($5.0$), Polichinelo ($6.0$).
  - *Média intensidade:* Flexão ($3.8$), Stiff ($4.0$), Afundo ($4.0$), Barra Fixa ($4.0$), Bom Dia ($3.5$), Agachamento Isométrico ($4.5$), Pranchas ($3.5$).
  - *Membros superiores e isolados:* Rosca Bíceps ($2.8$), Rosca Martelo ($2.8$), Desenvolvimento ($3.0$), Supino ($3.0$), Remadas ($3.0 - 3.5$), Tríceps ($3.0$), Elevações ($2.8$).

