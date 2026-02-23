import sys
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU
from datetime import datetime
import psutil
import json
import logging
import time
import subprocess
import wmi
import os
import threading

# Файл куда пишется мониторинг
log_file = "start_times.txt"

# Когда запустил
with open(log_file, "w", encoding="utf-8") as f:
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f.write(f"%%% МОНИТОРИНГ СИСТЕМЫ %%%\n")
    f.write("=" * 40 + "\n")
    f.write(f"Скрипт запущен: {current_time}\n")
    f.write("=" * 40 + "\n\n")

start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"\nМониторинг начат в {start_time}")
print("")


# Оперативная память:
def check_ram_health_windows():
    cmd = '''powershell "Get-WmiObject -Class Win32_PhysicalMemory | Select-Object @{Name='Производитель';Expression={$_.Manufacturer}}, @{Name='Описание';Expression={$_.Description}}, @{Name='Емкость (GB)';Expression={[math]::Round($_.Capacity/1GB, 2)}}, @{Name='Скорость (MHz)';Expression={$_.Speed}}, @{Name='Тип';Expression={$_.MemoryType}}, @{Name='Слот';Expression={$_.DeviceLocator}}, @{Name='Серийный номер';Expression={$_.SerialNumber}} | Format-Table -AutoSize"'''

    print("\nОПЕРАТИВНАЯ ПАМЯТЬ (RAM):")
    print("=" * 110)

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp866')
        output = result.stdout.rstrip('\n').rstrip('\r')
        if output.strip():
            print(output.strip())
        else:
            print("Нет информации об оперативной памяти")
        print("=" * 110)
    except Exception as e:
        print(f"Ошибка выполнения команды: {e}")
        print("=" * 110)


check_ram_health_windows()
print("")


# Диски:
def check_disk_health_windows():
    cmd = '''powershell "Get-PhysicalDisk | Select-Object @{Name='Имя диска';Expression={$_.FriendlyName}}, @{Name='Тип носителя';Expression={$_.MediaType}}, @{Name='Статус работы';Expression={$_.OperationalStatus}}, @{Name='Состояние здоровья';Expression={$_.HealthStatus}}, @{Name='Размер (GB)';Expression={[math]::Round($_.Size/1GB, 2)}} | Format-Table -AutoSize"'''

    print("\nФИЗИЧЕСКИЕ ДИСКИ:")
    print("=" * 110)

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp866')
        output = result.stdout.rstrip('\n').rstrip('\r')  # убрать пустые строки
        if output.strip():
            print(output.strip())
        else:
            print("Нет информации о физических дисках")
        print("=" * 110)
    except Exception as e:
        print(f"Ошибка выполнения команды: {e}")
        print("=" * 110)


check_disk_health_windows()
print("")


# Процессор:
def check_cpu_info_windows():
    cmd = 'powershell "Get-WmiObject Win32_Processor | Select-Object @{Name=\'Название\';Expression={$_.Name}}, @{Name=\'Количество ядер\';Expression={$_.NumberOfCores}}, @{Name=\'Количество потоков\';Expression={$_.NumberOfLogicalProcessors}}, @{Name=\'Макс. частота (ГГц)\';Expression={[math]::Round($_.MaxClockSpeed/1000, 2)}}, @{Name=\'Тек. частота (ГГц)\';Expression={[math]::Round($_.CurrentClockSpeed/1000, 2)}} | Format-List"'

    print("\nПРОЦЕССОР:")
    print("=" * 110)

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp866')
        output = result.stdout.strip()
        if output:
            print(output)
        else:
            print("Нет информации о процессоре")
        print("=" * 110)
    except Exception as e:
        print(f"Ошибка выполнения команды: {e}")
        print("=" * 110)


check_cpu_info_windows()
print("")


# Видеокарты:
def check_gpu_info_wmi():
    print("\nВИДЕОКАРТА:")
    print("=" * 110)

    try:
        c = wmi.WMI()
        video_controllers = c.Win32_VideoController()

        if not video_controllers:
            print("Нет информации о видеокартах")
            return

        output_lines = []
        for i, gpu in enumerate(video_controllers, 1):
            gpu_info = [f"[Видеокарта #{i}]"]
            gpu_info.append(f"Название: {gpu.Name}")
            gpu_info.append(f"Производитель: {gpu.AdapterCompatibility}")

            if gpu.AdapterRAM:
                memory_mb = round(int(gpu.AdapterRAM) / (1024 * 1024), 2)
                gpu_info.append(f"Видеопамять: {memory_mb} МБ")

            if gpu.CurrentHorizontalResolution and gpu.CurrentVerticalResolution:
                gpu_info.append(
                    f"Текущее разрешение: {gpu.CurrentHorizontalResolution}x{gpu.CurrentVerticalResolution}")

            if gpu.DriverVersion:
                gpu_info.append(f"Версия драйвера: {gpu.DriverVersion}")

            if gpu.DriverDate:
                gpu_info.append(f"Дата драйвера: {gpu.DriverDate}")

            output_lines.append("\n".join(gpu_info))

        print("\n".join(output_lines))
        print("=" * 110)

    except Exception as e:
        print(f"Ошибка получения информации: {e}")
        print("=" * 110)


check_gpu_info_wmi()
print("")


class SimpleMonitor:
    def __init__(self, config_file):
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger()
        self.log_file = log_file  # Путь к файлу

        self.running = True  # Флаг для контроля работы мониторинга
        self.stopped_already = False  # Флаг чтобы stop() не выполнялся дважды

        # Есть ли видюха
        try:
            nvmlInit()
            self.has_vidiokart = True
            self.vidiokart_handle = nvmlDeviceGetHandleByIndex(0)
            print("Видеокарта обнаружена")
            print("")

        except Exception as zzzzz:
            print(f"Видеокарта не обнаружена или ошибка NVML: {zzzzz}")
            print("")
            self.has_vidiokart = False

    def get_gpu_temp_vidiokart(self):
        # Получение температуры видеокарты
        if not self.has_vidiokart:
            return None

        try:
            temp_vidiokart = nvmlDeviceGetTemperature(self.vidiokart_handle, NVML_TEMPERATURE_GPU)
            return temp_vidiokart
        except Exception as zzz:
            print(f"Ошибка при получении температуры видеокарты: {zzz}")
            return None

    def check(self):
        if not self.running:
            return False

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        vidiokart_temp = self.get_gpu_temp_vidiokart()

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Вывод в питон
        if vidiokart_temp is not None:
            output_str = f"[{current_time}] CPU: {cpu:.1f}%, RAM: {ram:.1f}%, TEMP_VIDIOKART: {vidiokart_temp}°C"
        else:
            output_str = f"[{current_time}] CPU: {cpu:.1f}%, RAM: {ram:.1f}%, TEMP_VIDIOKART: Не найдена видеокарта!"

        print(output_str)

        # Запись в файл
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(output_str + "\n")

        # Мониторинг до макс
        if cpu > self.config.get('CPU_Usage', 90):
            warning = f"ПРЕДУПРЕЖДЕНИЕ: CPU превышен! ({cpu:.1f}%)"
            print(warning)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{warning}\n")

        if ram > self.config.get('RAM_Usage', 85):
            warning = f"ПРЕДУПРЕЖДЕНИЕ: RAM превышен! ({ram:.1f}%)"
            print(warning)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{warning}\n")

        if vidiokart_temp is not None and vidiokart_temp > self.config.get('GPU_Temp', 85):
            warning = f"ПРЕДУПРЕЖДЕНИЕ: Температура GPU высокая! ({vidiokart_temp}°C)"
            print(warning)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{warning}\n")

        return True

    def run(self):
        try:
            while self.running:
                if not self.check():
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        # Защита от повторного вызова
        if self.stopped_already:
            return

        self.stopped_already = True
        self.running = False

        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\nМониторинг остановлен в {end_time}")

        # Время завершения в файле
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 40 + "\n")
            f.write(f"Мониторинг остановлен: {end_time}\n")
            f.write("=" * 40 + "\n")


def wait_for_enter(monitor):
    # Функция для ожидания нажатия Enter #
    print("\n" + "=" * 60)
    print("Мониторинг запущен. Нажмите Enter для остановки...")
    print("=" * 60 + "\n")
    input()  # Ждем нажатия Enter
    monitor.stop()


# Запуск
if __name__ == "__main__":
    config = {"CPU_Usage": 90.0, "RAM_Usage": 85.0}
    with open("simple_config.json", "w") as f:
        json.dump(config, f)

    monitor = SimpleMonitor("simple_config.json")

    # Запускаем ожидание Enter
    enter_thread = threading.Thread(target=wait_for_enter, args=(monitor,), daemon=True)
    enter_thread.start()

    # Запускаем основной мониторинг
    monitor.run()

    # Удаляем конфиг файл
    os.remove("simple_config.json")

    # Ждем завершения потока с Enter (на всякий случай)
    enter_thread.join(timeout=1)

    # Ожидание перед выходом из EXE
    print("\n" + "=" * 60)
    print("Программа завершена. Нажмите Enter для выхода...")
    input()


