import sys
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

try:
    from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU

    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    print("pynvml не установлен, мониторинг GPU будет ограничен")

from datetime import datetime
import psutil
import json
import logging
import time
import subprocess
import os
import threading
from plyer import notification

# Файл куда пишется мониторинг
log_file = "start_times.txt"


def safe_subprocess_run(command):
    """Безопасный запуск subprocess с обработкой ошибок кодировки"""
    try:
        # Пробуем разные кодировки
        encodings = ['cp866', 'cp1251', 'utf-8']
        for encoding in encodings:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding=encoding
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout
            except UnicodeDecodeError:
                continue
        return ""
    except Exception as e:
        print(f"Ошибка выполнения команды: {e}")
        return ""


# Когда запустил
try:
    with open(log_file, "w", encoding="utf-8") as f:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"%%% МОНИТОРИНГ СИСТЕМЫ %%%\n")
        f.write("=" * 40 + "\n")
        f.write(f"Скрипт запущен: {current_time}\n")
        f.write("=" * 40 + "\n\n")
except Exception as e:
    print(f"Ошибка создания лог-файла: {e}")

start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"\nМониторинг начат в {start_time}")
print("")


# Оперативная память:
def check_ram_health_windows():
    cmd = '''powershell "Get-WmiObject -Class Win32_PhysicalMemory | Select-Object @{Name='Производитель';Expression={$_.Manufacturer}}, @{Name='Описание';Expression={$_.Description}}, @{Name='Емкость (GB)';Expression={[math]::Round($_.Capacity/1GB, 2)}}, @{Name='Скорость (MHz)';Expression={$_.Speed}}, @{Name='Тип';Expression={$_.MemoryType}}, @{Name='Слот';Expression={$_.DeviceLocator}}, @{Name='Серийный номер';Expression={$_.SerialNumber}} | Format-Table -AutoSize"'''

    print("\nОПЕРАТИВНАЯ ПАМЯТЬ (RAM):")
    print("=" * 110)

    try:
        output = safe_subprocess_run(cmd)
        if output.strip():
            print(output.strip())
        else:
            print("Нет информации об оперативной памяти")
    except Exception as e:
        print(f"Ошибка получения информации о RAM: {e}")
    finally:
        print("=" * 110)


# Диски:
def check_disk_health_windows():
    cmd = '''powershell "Get-PhysicalDisk | Select-Object @{Name='Имя диска';Expression={$_.FriendlyName}}, @{Name='Тип носителя';Expression={$_.MediaType}}, @{Name='Статус работы';Expression={$_.OperationalStatus}}, @{Name='Состояние здоровья';Expression={$_.HealthStatus}}, @{Name='Размер (GB)';Expression={[math]::Round($_.Size/1GB, 2)}} | Format-Table -AutoSize"'''

    print("\nФИЗИЧЕСКИЕ ДИСКИ:")
    print("=" * 110)

    try:
        output = safe_subprocess_run(cmd)
        if output.strip():
            print(output.strip())
        else:
            print("Нет информации о физических дисках")
    except Exception as e:
        print(f"Ошибка получения информации о дисках: {e}")
    finally:
        print("=" * 110)


# Процессор:
def check_cpu_info_windows():
    cmd = 'powershell "Get-WmiObject Win32_Processor | Select-Object @{Name=\'Название\';Expression={$_.Name}}, @{Name=\'Количество ядер\';Expression={$_.NumberOfCores}}, @{Name=\'Количество потоков\';Expression={$_.NumberOfLogicalProcessors}}, @{Name=\'Макс. частота (ГГц)\';Expression={[math]::Round($_.MaxClockSpeed/1000, 2)}}, @{Name=\'Тек. частота (ГГц)\';Expression={[math]::Round($_.CurrentClockSpeed/1000, 2)}} | Format-List"'''

    print("\nПРОЦЕССОР:")
    print("=" * 110)

    try:
        output = safe_subprocess_run(cmd)
        if output.strip():
            # Убираем лишние пустые строки в начале и конце #
            lines = output.strip().split('\n')
            # Фильтруем строки, убираем полностью пустые строки #
            filtered_lines = [line for line in lines if line.strip() != '']
            print('\n'.join(filtered_lines))
        else:
            print("Нет информации о процессоре")
    except Exception as e:
        print(f"Ошибка получения информации о процессоре: {e}")
    finally:
        print("=" * 110)


# Видеокарты:
def check_gpu_info_wmi():
    print("\nВИДЕОКАРТА:")
    print("=" * 110)

    try:
        import wmi
        c = wmi.WMI()
        video_controllers = c.Win32_VideoController()

        if not video_controllers:
            print("Нет информации о видеокартах")
            return

        output_lines = []
        for i, gpu in enumerate(video_controllers, 1):
            gpu_info = [f"[Видеокарта #{i}]"]

            # Безопасное получение атрибутов
            if hasattr(gpu, 'Name') and gpu.Name:
                gpu_info.append(f"Название: {gpu.Name}")

            if hasattr(gpu, 'AdapterCompatibility') and gpu.AdapterCompatibility:
                gpu_info.append(f"Производитель: {gpu.AdapterCompatibility}")

            if hasattr(gpu, 'AdapterRAM') and gpu.AdapterRAM:
                try:
                    memory_mb = round(int(gpu.AdapterRAM) / (1024 * 1024), 2)
                    gpu_info.append(f"Видеопамять: {memory_mb} МБ")
                except:
                    pass

            if hasattr(gpu, 'CurrentHorizontalResolution') and hasattr(gpu, 'CurrentVerticalResolution'):
                if gpu.CurrentHorizontalResolution and gpu.CurrentVerticalResolution:
                    gpu_info.append(
                        f"Текущее разрешение: {gpu.CurrentHorizontalResolution}x{gpu.CurrentVerticalResolution}")

            output_lines.append("\n".join(gpu_info))

        if output_lines:
            print("\n".join(output_lines))
        else:
            print("Не удалось получить информацию о видеокартах")

    except ImportError:
        print("Модуль wmi не установлен. Установите: pip install wmi")
    except Exception as e:
        print(f"Ошибка получения информации о видеокарте: {e}")
    finally:
        print("=" * 110)


# Вызов функций с обработкой ошибок
try:
    check_ram_health_windows()
    print("")
    check_disk_health_windows()
    print("")
    check_cpu_info_windows()
    print("")
    check_gpu_info_wmi()
    print("")
except Exception as e:
    print(f"Общая ошибка при сборе информации: {e}")


class SimpleMonitor:
    def __init__(self, config_file):
        # Загрузка конфигурации
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"ОШИБКА: Не удалось загрузить конфигурационный файл {config_file}")
            print(f"Ошибка: {e}")
            print("Программа не может продолжить работу без конфигурационного файла.")
            sys.exit(1)

        # Проверка наличия всех необходимых параметров в конфиге
        required_params = ['CPU_Usage', 'RAM_Usage', 'GPU_Temp']
        for param in required_params:
            if param not in self.config:
                print(f"ОШИБКА: В конфигурационном файле отсутствует параметр {param}")
                sys.exit(1)

        # Настройка логирования
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self.logger = logging.getLogger()
        except Exception as e:
            print(f"Ошибка настройки логирования: {e}")
            self.logger = None

        self.log_file = log_file
        self.running = True
        self.stopped_already = False

        # Проверка наличия видеокарты через NVML
        self.has_vidiokart = False
        self.vidiokart_handle = None

        if NVML_AVAILABLE:
            try:
                nvmlInit()
                self.vidiokart_handle = nvmlDeviceGetHandleByIndex(0)
                self.has_vidiokart = True
                print("Видеокарта обнаружена через NVML")
            except Exception as e:
                print(f"Видеокарта не обнаружена или ошибка NVML: {e}")
        else:
            print("NVML не доступен, температура GPU не будет отслеживаться")

        # Вывод загруженных пороговых значений
        print(f"\nЗагружены пороговые значения из конфига:")
        print(f"  CPU: {self.config['CPU_Usage']}%")
        print(f"  RAM: {self.config['RAM_Usage']}%")
        print(f"  GPU Temperature: {self.config['GPU_Temp']}°C")
        print("")

    def get_gpu_temp_vidiokart(self):
        if not self.has_vidiokart or not self.vidiokart_handle:
            return None

        try:
            temp_vidiokart = nvmlDeviceGetTemperature(self.vidiokart_handle, NVML_TEMPERATURE_GPU)
            return temp_vidiokart
        except Exception as e:
            print(f"Ошибка при получении температуры видеокарты: {e}")
            return None

    def check(self):
        if not self.running:
            return False

        try:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            vidiokart_temp = self.get_gpu_temp_vidiokart()

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Вывод в консоль
            if vidiokart_temp is not None:
                output_str = f"[{current_time}] CPU: {cpu:.1f}%, RAM: {ram:.1f}%, TEMP_VIDIOKART: {vidiokart_temp}°C"
            else:
                output_str = f"[{current_time}] CPU: {cpu:.1f}%, RAM: {ram:.1f}%, TEMP_VIDIOKART: Не доступна"

            print(output_str)

            # Запись в файл
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(output_str + "\n")
            except Exception as e:
                print(f"Ошибка записи в лог: {e}")

            # Проверка превышения порогов (значения берутся ТОЛЬКО из конфига)
            if cpu > self.config['CPU_Usage']:
                self.send_warning("CPU превышен!", f"CPU: {cpu:.1f}% (порог: {self.config['CPU_Usage']}%)")

            if ram > self.config['RAM_Usage']:
                self.send_warning("RAM превышен!", f"RAM: {ram:.1f}% (порог: {self.config['RAM_Usage']}%)")

            if vidiokart_temp is not None and vidiokart_temp > self.config['GPU_Temp']:
                self.send_warning("Температура видеокарты высокая!",
                                  f"Температура: {vidiokart_temp}°C (порог: {self.config['GPU_Temp']}°C)")

            return True

        except Exception as e:
            print(f"Ошибка в цикле мониторинга: {e}")
            return True  # Продолжаем работу даже при ошибке

    def send_warning(self, title, message):
        # Отправка предупреждения #
        warning = f"ПРЕДУПРЕЖДЕНИЕ: {title} ({message})"
        print(warning)

        try:
            notification.notify(
                title="ПРЕДУПРЕЖДЕНИЕ!!!",
                message=title,
                timeout=3
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{warning}\n")
        except Exception as e:
            pass

    def run(self):
        try:
            while self.running:
                if not self.check():
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Критическая ошибка в мониторинге: {e}")
        finally:
            self.stop()

    def stop(self):
        if self.stopped_already:
            return

        self.stopped_already = True
        self.running = False

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\nМониторинг остановлен в {end_time}")

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 40 + "\n")
                f.write(f"Мониторинг остановлен: {end_time}\n")
                f.write("=" * 40 + "\n")
        except Exception as e:
            pass


def wait_for_enter(monitor):
    print("\n" + "=" * 60)
    print("Мониторинг запущен. Нажмите Enter для остановки...")
    print("=" * 60 + "\n")
    try:
        input()
    except:
        pass
    monitor.stop()


# Запуск
if __name__ == "__main__":
    config_file = "simple_config.json"

    # Проверяем существование конфиг-файла
    if not os.path.exists(config_file):
        print(f"ОШИБКА: Файл конфигурации {config_file} не найден!")
        print("Создайте файл simple_config.json, например, со следующим содержимым:")
        print('{"CPU_Usage": 90.0, "RAM_Usage": 85.0, "GPU_Temp": 80.0}')
        print("\nНажмите Enter для выхода...")
        try:
            input()
        except:
            pass
        sys.exit(1)

    try:
        monitor = SimpleMonitor(config_file)

        # Запускаем ожидание Enter
        enter_thread = threading.Thread(target=wait_for_enter, args=(monitor,), daemon=True)
        enter_thread.start()

        # Запускаем основной мониторинг
        monitor.run()

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        # Ожидание перед выходом
        print("\n" + "=" * 60)
        print("Программа завершена. Нажмите Enter для выхода...")
        try:
            input()
        except:
            pass
