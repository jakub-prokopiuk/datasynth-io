from faker import Faker
from typing import List, Dict, Any, Set, Union
from models import GeneratorRequest
from openai import AsyncOpenAI
import random
import rstr
from jinja2 import Environment, BaseLoader
from unidecode import unidecode
try:
    from job_manager import job_manager
except ImportError:
    class MockJobManager:
        async def check_cancellation(self, job_id): pass
        def set_status(self, job_id, status): pass
        def set_total(self, job_id, total): pass
        def update_progress(self, job_id, progress): pass
    job_manager = MockJobManager()
import asyncio
import aiosqlite
import json
import uuid
import os
import httpx

class DotAccessWrapper:
    def __init__(self, data: Dict[str, Any]):
        self._data = data
    def __getattr__(self, item):
        if item in self._data: return self._data[item]
        return f"[Missing {item}]"
    def __getitem__(self, item): return self._data[item]
    def __str__(self): return str(self._data)
    def __repr__(self): return str(self._data)

class DataEngine:
    def __init__(self):
        self.faker = Faker()
        self.jinja_env = Environment(loader=BaseLoader())
        
        def filter_slugify(value, separator="."):
            if not isinstance(value, str): return str(value)
            clean = unidecode(value).lower().strip()
            return clean.replace(" ", separator)
            
        def filter_first_letter(value):
            if not isinstance(value, str) or not value: return ""
            return unidecode(value[0]).lower()

        self.jinja_env.filters['slugify'] = filter_slugify
        self.jinja_env.filters['first_letter'] = filter_first_letter

    def _generate_template_value(self, params: Dict[str, Any], current_row_context: Dict[str, Any]) -> str:
        template_str = params.get("template", "")
        try:
            template = self.jinja_env.from_string(template_str)
            return template.render(**current_row_context)
        except Exception as e:
            return f"Error: Template failed {str(e)}"

    def _generate_regex_value(self, params: Dict[str, Any]) -> str:
        pattern = params.get("pattern", r"[A-Z]{3}-\d{3}")
        try: return rstr.xeger(pattern)
        except Exception as e: return f"Error: Invalid Regex {str(e)}"

    def _generate_timestamp_value(self, params: Dict[str, Any], faker_instance: Faker) -> str:
        start = params.get("min_date", "-1y") 
        end = params.get("max_date", "now")
        fmt = params.get("format", "%Y-%m-%d %H:%M:%S")
        try:
            dt = faker_instance.date_time_between(start_date=start, end_date=end)
            if fmt == "iso": return dt.isoformat()
            elif fmt == "timestamp": return str(dt.timestamp())
            else: return dt.strftime(fmt)
        except Exception as e: return f"Error: Date gen failed {str(e)}"

    def _generate_integer_or_float_value(self, params: Dict[str, Any]) -> Union[int, float]:
            min_val = params.get("min", 0)
            max_val = params.get("max", 100)
            
            is_float = isinstance(min_val, float) or isinstance(max_val, float)
            
            if is_float:
                def get_precision(n):
                    s = str(n)
                    if '.' in s: return len(s.split('.')[1])
                    return 0
                
                precision = max(get_precision(min_val), get_precision(max_val))
                
                val = random.uniform(float(min_val), float(max_val))
                return round(val, precision)
            else:
                try: return random.randint(int(min_val), int(max_val))
                except ValueError: return 0

    def _generate_boolean_value(self, params: Dict[str, Any]) -> bool:
        probability = params.get("probability", 50)
        return random.random() * 100 < probability

    def _generate_faker_value(self, params: Dict[str, Any], faker_instance: Faker) -> Any:
        method_name = params.get("method")
        if not method_name: return None
        if not hasattr(faker_instance, method_name): return f"Error: Faker method '{method_name}' not found"
        faker_method = getattr(faker_instance, method_name)
        kwargs = params.get("kwargs", {})
        try: return faker_method(**kwargs)
        except Exception as e: return f"Error: {str(e)}"

    def _generate_distribution_value(self, params: Dict[str, Any]) -> Any:
        options = params.get("options")
        weights = params.get("weights")
        if not options or not isinstance(options, list): return "Error: options required"
        if not weights: return random.choice(options)
        if len(options) != len(weights): return "Error: options/weights mismatch"
        try: return random.choices(options, weights=weights, k=1)[0]
        except Exception as e: return f"Error: {str(e)}"

    async def _generate_foreign_key_value(self, params: Dict[str, Any], db: aiosqlite.Connection, table_id_to_name: Dict[str, str], avoid_values: Set[Any] = None) -> Any:
        target_table_id = params.get("table_id")
        target_column = params.get("column_name")
        if not target_table_id or not target_column or not db: return None 
        
        target_table_name = table_id_to_name.get(target_table_id, target_table_id)

        query = f'SELECT "{target_column}" FROM "{target_table_name}"'
        if avoid_values:
            avoid_list = "','".join(str(v).replace("'", "''") for v in avoid_values)
            query += f" WHERE \"{target_column}\" NOT IN ('{avoid_list}')"
        query += " ORDER BY RANDOM() LIMIT 1"
        
        try:
            async with db.execute(query) as cursor:
                row = await cursor.fetchone()
                if row:
                    val = row[0]
                    row_query = f'SELECT * FROM "{target_table_name}" WHERE "{target_column}" = ? LIMIT 1'
                    async with db.execute(row_query, (val,)) as row_cursor:
                        row_data = await row_cursor.fetchone()
                        columns = [col[0] for col in row_cursor.description]
                        parent_row = dict(zip(columns, row_data))
                        return (val, parent_row)
        except Exception as e:
            print(f"FK Error: {e}")
        return "Error: No unique FK values left"

    async def _generate_llm_batch_value(
        self, 
        params: Dict[str, Any], 
        contexts: List[Dict[str, Any]], 
        retry_count: int = 0
    ) -> List[str]:
        if not contexts: return []
        
        provider = params.get("provider", "openai")
        model = params.get("model", "gpt-4o-mini")
        template = params.get("prompt_template", "")
        
        base_temp = float(params.get("temperature", 1.0))
        top_p = float(params.get("top_p", 1.0))
        
        active_client = self.ollama_client if provider == "ollama" else self.openai_client
        temperature = min(base_temp + (retry_count * 0.1), 1.5)
        
        if not template: return ["Error: No prompt_template"] * len(contexts)
        
        SUB_BATCH_SIZE = 10
        MAX_CONCURRENT = 4
        sem = asyncio.Semaphore(MAX_CONCURRENT)
        
        async def _process_sub_batch(sub_contexts: List[Dict[str, Any]]) -> List[str]:
            combined_prompts = []
            for i, ctx in enumerate(sub_contexts):
                formatting_context = {k: DotAccessWrapper(v) if isinstance(v, dict) else v for k, v in ctx.items()}
                try:
                    formatted = template.format(**formatting_context)
                    combined_prompts.append(f"Row {i+1}:\n{formatted}")
                except Exception as e:
                    combined_prompts.append(f"Row {i+1}:\nError formatting prompt: {str(e)}")

            joined_prompt = "\n\n---\n\n".join(combined_prompts)
            
            system_msg = (
                "You are a synthetic data generator. Generate FICTIONAL, CREATIVE data. "
                f"You MUST output exactly a JSON array of {len(sub_contexts)} strings. "
                "Do NOT output markdown blocks, just the raw JSON array. "
                "Example: [\"review 1\", \"review 2\"]"
            )
            
            batch_failed = False
            async with sem:
                try:
                    response = await active_client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": joined_prompt}],
                        temperature=temperature, 
                        max_tokens=150 * len(sub_contexts), 
                        top_p=top_p,
                        timeout=httpx.Timeout(600.0, read=600.0, write=10.0, connect=5.0)
                    )
                    
                    content = response.choices[0].message.content.strip()
                    if content.startswith("```json"): content = content[7:]
                    if content.startswith("```"): content = content[3:]
                    if content.endswith("```"): content = content[:-3]
                    content = content.strip()
                    
                    parsed_array = json.loads(content)
                    
                    if isinstance(parsed_array, list) and len(parsed_array) == len(sub_contexts):
                        return [str(item) for item in parsed_array]
                    else:
                        print(f"Sub-batch length mismatch ({len(parsed_array)} vs {len(sub_contexts)}). Falling back.")
                        batch_failed = True
                        
                except Exception as e:
                    print(f"Sub-batch error ({str(e)}). Falling back for {len(sub_contexts)} rows.")
                    batch_failed = True
            
            if batch_failed:
                async def _single_llm_with_sem(ctx):
                    async with sem:
                        return await self._generate_llm_value(params, ctx, retry_count=retry_count)
                return await asyncio.gather(*[_single_llm_with_sem(ctx) for ctx in sub_contexts])
        
        sub_batches = [contexts[i:i + SUB_BATCH_SIZE] for i in range(0, len(contexts), SUB_BATCH_SIZE)]
        sub_batch_results = await asyncio.gather(*[_process_sub_batch(sb) for sb in sub_batches])
        
        all_results = []
        for batch_result in sub_batch_results:
            all_results.extend(batch_result)
        
        print(f"Generated {len(all_results)} rows via {provider} (sub-batches of {SUB_BATCH_SIZE}, {MAX_CONCURRENT} concurrent)")
        return all_results

    async def _generate_llm_value(self, params: Dict[str, Any], current_row_context: Dict[str, Any], avoid_values: Set[str] = None, retry_count: int = 0) -> str:
        provider = params.get("provider", "openai")
        model = params.get("model", "gpt-4o-mini")
        template = params.get("prompt_template", "")
        
        base_temp = float(params.get("temperature", 1.0))
        top_p = float(params.get("top_p", 1.0))
        
        active_client = self.ollama_client if provider == "ollama" else self.openai_client
        
        temperature = min(base_temp + (retry_count * 0.1), 1.5)
        
        if not template: return "Error: No prompt_template"
        
        formatting_context = {}
        for k, v in current_row_context.items():
            if isinstance(v, dict): formatting_context[k] = DotAccessWrapper(v)
            else: formatting_context[k] = v
            
        try:
            formatted_prompt = template.format(**formatting_context)
            if avoid_values and len(avoid_values) > 0:
                avoid_list_str = ", ".join(list(avoid_values)[-10:])
                formatted_prompt += f"\n\nCONSTRAINT: Value MUST be unique. DO NOT use: {avoid_list_str}."
        except Exception as e: return f"Error formatting prompt: {str(e)}"
        try:
            system_msg = "You are a synthetic data generator. Generate FICTIONAL, CREATIVE data. Output ONE single value."
            response = await active_client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": formatted_prompt}],
                temperature=temperature, 
                max_tokens=150, 
                top_p=top_p,
                timeout=httpx.Timeout(600.0, read=600.0, write=10.0, connect=5.0)
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e: 
            return f"{provider.capitalize()} Error: {str(e)}"

    def _resolve_generation_order(self, tables: List[Any]) -> List[Any]:
        id_to_table = {t.id: t for t in tables}
        dependencies = {t.id: set() for t in tables}
        for table in tables:
            for field in table.fields:
                if field.type == "foreign_key":
                    target_id = field.params.get("table_id")
                    if target_id and target_id in id_to_table and target_id != table.id:
                        dependencies[table.id].add(target_id)
        ordered_tables = []
        while dependencies:
            ready_tables = [t_id for t_id, deps in dependencies.items() if not deps]
            if not ready_tables:
                remaining = list(dependencies.keys())
                for t_id in remaining: ordered_tables.append(id_to_table[t_id])
                break
            ready_tables.sort()
            for t_id in ready_tables:
                ordered_tables.append(id_to_table[t_id])
                del dependencies[t_id]
            for t_id in dependencies:
                dependencies[t_id] = dependencies[t_id] - set(ready_tables)
        return ordered_tables

    async def generate(self, request: GeneratorRequest, job_id: str = None) -> str:
        table_id_to_name = {t.id: t.name for t in request.tables}
        ordered_tables = self._resolve_generation_order(request.tables)

        requested_locale = request.config.locale or "en_US"
        try: job_faker = Faker(requested_locale)
        except Exception: job_faker = Faker("en_US")

        total_rows_to_gen = sum(t.rows_count for t in request.tables)
        current_rows_gen = 0
        
        self.openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "dummy_key_not_used"))
        ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434/v1")
        self.ollama_client = AsyncOpenAI(base_url=ollama_host, api_key="ollama")

        async def _safe_job_manager_call(method_name, *args):
            if hasattr(job_manager, method_name):
                func = getattr(job_manager, method_name)
                if asyncio.iscoroutinefunction(func):
                    await func(*args)
                else:
                    func(*args)

        if job_id:
            await _safe_job_manager_call("set_status", job_id, "generating")
            await _safe_job_manager_call("set_total", job_id, total_rows_to_gen)
            await _safe_job_manager_call("update_progress", job_id, 0)
        
        db_path = f"outputs/{job_id}.db" if job_id else f"outputs/temp_{uuid.uuid4().hex}.db"

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        async with aiosqlite.connect(db_path) as db:
            for table in ordered_tables:
                columns_def = []
                for field in table.fields:
                    columns_def.append(f'"{field.name}" TEXT')
                
                columns_str = ", ".join(columns_def)
                create_query = f'CREATE TABLE IF NOT EXISTS "{table.name}" (_row_id INTEGER PRIMARY KEY AUTOINCREMENT, {columns_str})'
                await db.execute(create_query)
            await db.commit()

            for table in ordered_tables:
                unique_tracker: Dict[str, set] = {}
                for field in table.fields:
                    if field.is_unique: unique_tracker[field.name] = set()

                rows_generated_for_table = 0
                BATCH_SIZE = 100

                while rows_generated_for_table < table.rows_count:
                    if job_id:
                        await _safe_job_manager_call("check_cancellation", job_id)
                        await asyncio.sleep(0.01) 

                    remaining = table.rows_count - rows_generated_for_table
                    current_batch = min(BATCH_SIZE, remaining)

                    tasks = []
                    for _ in range(current_batch):
                        tasks.append(self._generate_single_row(
                            table=table,
                            global_context=request.config.global_context,
                            unique_tracker=unique_tracker,
                            job_faker=job_faker,
                            db=db,
                            table_id_to_name=table_id_to_name,
                            job_id=job_id,
                            skip_llm=True
                        ))
                    
                    batch_results = await asyncio.gather(*tasks)
                    
                    llm_fields = [f for f in table.fields if f.type == "llm"]
                    if llm_fields and batch_results:
                        for field in llm_fields:
                            contexts = []
                            for row in batch_results:
                                ctx = {k: v for k, v in row.items()}
                                if request.config.global_context:
                                    ctx["global_context"] = request.config.global_context
                                contexts.append(ctx)
                            
                            llm_results = await self._generate_llm_batch_value(field.params, contexts)
                            
                            for i, row in enumerate(batch_results):
                                row[field.name] = llm_results[i]
                            
                            if job_id and total_rows_to_gen > 0:
                                percent = int((current_rows_gen + current_batch) / total_rows_to_gen * 100)
                                await _safe_job_manager_call("update_progress", job_id, percent)
                    
                    if batch_results:
                        column_names = [field.name for field in table.fields]
                        placeholders = ", ".join(["?"] * len(column_names))
                        columns_joined = '", "'.join(column_names)
                        insert_query = f'INSERT INTO "{table.name}" ("{columns_joined}") VALUES ({placeholders})'
                        
                        insert_data = []
                        for row in batch_results:
                            row_tuple = []
                            for col in column_names:
                                val = row.get(col)
                                if isinstance(val, (dict, list)): val = json.dumps(val)
                                else: val = str(val) if val is not None else None
                                row_tuple.append(val)
                            insert_data.append(tuple(row_tuple))
                        
                        await db.executemany(insert_query, insert_data)
                        await db.commit()
                    
                    rows_generated_for_table += current_batch
                    current_rows_gen += current_batch
                    
                    if job_id and total_rows_to_gen > 0:
                        percent = int((current_rows_gen / total_rows_to_gen) * 100)
                        await _safe_job_manager_call("update_progress", job_id, percent)

        await self.openai_client.close()
        await self.ollama_client.close()
        
        return db_path

    async def _generate_single_row(
        self, 
        table: Any, 
        global_context: str, 
        unique_tracker: Dict[str, Set[Any]], 
        job_faker: Faker, 
        db: aiosqlite.Connection,
        table_id_to_name: Dict[str, str],
        job_id: str = None,
        skip_llm: bool = False
    ) -> Dict[str, Any]:
        
        row_data = {}         
        context_data = {}     
        if global_context: context_data["global_context"] = global_context

        for field in table.fields:
            if job_id:
                # We need to access _safe_job_manager_call which is inside generate.
                # Actually, check_cancellation isn't strictly necessary outside generate,
                # but let's safely call job_manager directly if it has it, or just pass.
                if hasattr(job_manager, "check_cancellation"):
                    func = job_manager.check_cancellation
                    if asyncio.iscoroutinefunction(func):
                        await func(job_id)
                    else:
                        func(job_id)
            max_retries = 10 
            attempts = 0
            final_value = None
            current_avoid_list = set()
            if field.is_unique: current_avoid_list.update(unique_tracker[field.name])
            
            while attempts < max_retries:
                generated_val = None
                
                if field.type == "faker": generated_val = self._generate_faker_value(field.params, job_faker)
                elif field.type == "timestamp": generated_val = self._generate_timestamp_value(field.params, job_faker)
                elif field.type == "foreign_key":
                    result = await self._generate_foreign_key_value(field.params, db, table_id_to_name, current_avoid_list)
                    if result and not isinstance(result, str):
                        val, parent_row = result
                        generated_val = val
                        context_data[field.name] = parent_row 
                    else: generated_val = result if result else "Error: FK Failed"
                elif field.type == "distribution": generated_val = self._generate_distribution_value(field.params)
                elif field.type == "integer": generated_val = self._generate_integer_or_float_value(field.params)
                elif field.type == "boolean": generated_val = self._generate_boolean_value(field.params)
                elif field.type == "regex": generated_val = self._generate_regex_value(field.params)
                
                elif field.type == "llm": 
                    if skip_llm:
                        final_value = None  
                        break 
                    generated_val = await self._generate_llm_value(field.params, context_data, current_avoid_list, attempts)
                
                elif field.type == "template": generated_val = self._generate_template_value(field.params, context_data)
                
                if field.is_unique:
                    if generated_val not in unique_tracker[field.name] and "Error" not in str(generated_val):
                        if skip_llm and field.type == "llm":
                            pass 
                        else:
                            unique_tracker[field.name].add(generated_val)
                            final_value = generated_val
                            break
                    else:
                        if skip_llm and field.type == "llm":
                            break 
                        attempts += 1
                        if field.type == "foreign_key" and "Error" in str(generated_val):
                            final_value = generated_val
                            break
                        current_avoid_list.add(generated_val)
                else:
                    final_value = generated_val
                    break

            if field.is_unique and attempts == max_retries: final_value = f"Error: Uniqueness failed for {field.name}"
            
            row_data[field.name] = final_value
            if field.type != "foreign_key": context_data[field.name] = final_value
            
        return row_data
