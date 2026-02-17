from faker import Faker
from typing import List, Dict, Any, Set, Union
from models import GeneratorRequest
from openai import OpenAI, AsyncOpenAI
import random
import rstr
from jinja2 import Environment, BaseLoader
from unidecode import unidecode
from job_manager import job_manager
import asyncio

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
        self.client = OpenAI() 
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

    def _generate_foreign_key_value(self, params: Dict[str, Any], all_generated_data: Dict[str, List[Dict[str, Any]]], avoid_values: Set[Any] = None) -> Any:
        target_table_id = params.get("table_id")
        target_column = params.get("column_name")
        if not target_table_id or not target_column: return None 
        if target_table_id not in all_generated_data: return None 
        source_rows = all_generated_data[target_table_id]
        if not source_rows: return None
        available_rows = source_rows
        if avoid_values:
            available_rows = [row for row in source_rows if row.get(target_column) not in avoid_values]
        if not available_rows: return "Error: No unique FK values left"
        random_row = random.choice(available_rows)
        return (random_row.get(target_column), random_row)

    async def _generate_llm_value(self, params: Dict[str, Any], current_row_context: Dict[str, Any], avoid_values: Set[str] = None, retry_count: int = 0) -> str:
        provider = params.get("provider", "openai")
        model = params.get("model", "gpt-4o-mini")
        template = params.get("prompt_template", "")
        
        base_temp = float(params.get("temperature", 1.0))
        top_p = float(params.get("top_p", 1.0))
        
        if provider == "ollama":
            active_client = AsyncOpenAI(
                base_url="http://ollama:11434/v1",
                api_key="ollama" 
            )
        else:
            active_client = AsyncOpenAI()
        
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
                top_p=top_p
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

    async def generate(self, request: GeneratorRequest, job_id: str = None) -> Dict[str, List[Dict[str, Any]]]:
        generated_tables_data: Dict[str, List[Dict[str, Any]]] = {}
        table_id_to_name = {t.id: t.name for t in request.tables}
        ordered_tables = self._resolve_generation_order(request.tables)

        requested_locale = request.config.locale or "en_US"
        try: job_faker = Faker(requested_locale)
        except Exception: job_faker = Faker("en_US")

        total_rows_to_gen = sum(t.rows_count for t in request.tables)
        current_rows_gen = 0
        
        if job_id:
            job_manager.set_total(job_id, total_rows_to_gen)
            job_manager.update_progress(job_id, 0) 

        for table in ordered_tables:
            table_rows = []
            unique_tracker: Dict[str, set] = {}
            for field in table.fields:
                if field.is_unique: unique_tracker[field.name] = set()

            rows_generated_for_table = 0
            
            BATCH_SIZE = 10

            while rows_generated_for_table < table.rows_count:
                if job_id:
                    await job_manager.check_cancellation(job_id)
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
                        generated_tables_data=generated_tables_data
                    ))
                
                batch_results = await asyncio.gather(*tasks)
                table_rows.extend(batch_results)
                
                rows_generated_for_table += current_batch
                current_rows_gen += current_batch
                
                if job_id and total_rows_to_gen > 0:
                    percent = int((current_rows_gen / total_rows_to_gen) * 100)
                    job_manager.update_progress(job_id, percent)

            generated_tables_data[table.id] = table_rows

        final_output = {}
        for t_id, rows in generated_tables_data.items():
            t_name = table_id_to_name.get(t_id, t_id)
            final_output[t_name] = rows
        return final_output

    async def _generate_single_row(
        self, 
        table: Any, 
        global_context: str, 
        unique_tracker: Dict[str, Set[Any]], 
        job_faker: Faker, 
        generated_tables_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        
        row_data = {}         
        context_data = {}     
        if global_context: context_data["global_context"] = global_context

        for field in table.fields:
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
                    result = self._generate_foreign_key_value(field.params, generated_tables_data, current_avoid_list)
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
                    generated_val = await self._generate_llm_value(field.params, context_data, current_avoid_list, attempts)
                
                elif field.type == "template": generated_val = self._generate_template_value(field.params, context_data)
                
                if field.is_unique:
                    if generated_val not in unique_tracker[field.name] and "Error" not in str(generated_val):
                        unique_tracker[field.name].add(generated_val)
                        final_value = generated_val
                        break
                    else:
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