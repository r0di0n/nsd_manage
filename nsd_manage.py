# coding: utf-8
"""
Скрипт предназначен для генерации и обновления ДНС зон используя значения по
умолчанию и базовые файлы в которых перечислены иные значения поддоменов и
других записей. Для добавления зоны необходимо создать файл вида domain.com в
path_gen. В нем перечислить величины и значения которые при генерации должны
заменить значения по умолчанию. Неперечисленные велечины унаследуют значения
указанные по умолчанию."""
#TODO: Необходимо переписать словарь, разделив А записи и остальное
#MX записи и приоритеты, задавать порядковым номером (MX MX1 MX2 ... )
#IPv6
#RTP
#Удаление зоны?
#Добавление во входные конфиги, данных с которыми были созданы зоны. Т.к.
#данные по умолчанию могут изменяться со временем.

import os
import random
import re
import sys
import time

from config import Config


def main():
    #Задаем значения используемые для генерации файлов зон, возможно надо
    #брать из внешнего конфига.
    "DEFAULT VALUES"
    defaults = {
        'A': '192.168.0.163',
        'MX': '192.168.0.164',
        'www': '192.168.0.163',
        'mail': '192.168.0.164',

        'NS1_IP': ['192.168.0.165', '192.168.1.165'],
        'NS2_IP': ['192.168.0.166', '192.168.1.166'],
        'NS1': 'ns1.domain.ru',
        'NS2': 'ns2.domain.ru'}

    path_master = './etc/nsd/zones/master/'
    path_slave = './etc/nsd/zones/slave/'
    paths = {'master': path_master, 'slave': path_slave}
    path_gen = './etc/nsd/gen/'
    path_zone = './etc/nsd/zones.conf'
    path_zone_slave = './etc/nsd/zones_slave.conf'
    file1 = path_gen + 'domain.com'

    workonfiles = os.listdir(path_gen)
    masterzones = os.listdir(path_master)
    slavezones = os.listdir(path_slave)

    #Обойдем все файлы конфигов зон и сгенерируем по необходимости секции
    #для zones.conf и файлы зон.
    for name in workonfiles:
        #Далее используется парсер конфигов - пакет config
        # http://www.red-dove.com/config-doc/ (pip install config)
        f = file(path_gen + name)
        cfg = Config(f)
        #Соединяем значения заданные по-умолчанию и обозначенные в конфиге,
        #приоритет у тех что в конфиге.
        values = gen_values(name, cfg, defaults)
        #Проверить есть ли ключи от зоны, если нет то сделать и записать.
        with open(path_zone, 'r') as key_file:
            key_data_r = key_file.read()

        # Поиск в zones.conf по строчке с именем зоны, если нет упоминания,
        # добавляем:
        sample = 'name:\s*\"(%s)\"' % name
        result = re.findall(sample, key_data_r)
        if result.count(name) > 0:
            pass
        else:
            key_data = make_key(name, values, paths)

            with open(path_zone, 'a') as key_file:
                for line in key_data['master']:
                    key_file.write('%s\n' % str(line))
            with open(path_zone_slave, 'a') as key_file:
                for line in key_data['slave']:
                    key_file.write('%s\n' % str(line))

        #Генерируем содержимое файла зоны:
        zone_data = make_zone(values, name)
        with open(path_master + name, 'w') as zone_file:
            for line in zone_data:
                zone_file.write('%s\n' % str(line))


#Объединение значений по-умолчанию и данных из конфига зоны:
def gen_values(name, cfg, defaults):
    values = {}
    values.update(defaults)
    #values['root'] = name

    #переназначение дефолтных значений:
    for i in defaults.keys():
        if i in cfg.keys():
            values[i] = cfg.get(i)
    #добавление значений из конфига:
    for i in cfg.keys():
        #возможность указывать в конфиге вместо IP пустое место
        # или "А" для использования IP от А записи
        if i not in defaults.keys():
            if cfg.get(i) == '':
                values[i] = values['A']
            else:
                values[i] = cfg.get(i)
    return values


#Генерация куска конфига nsd для зоны (Надобно разделить для мастера и слейва):
def make_key(name, values, paths):
    secret = ''.join(random.choice('0123456789ABCDEF')
                     for i in range(16)).encode('base64').strip()
    ns1_ips = values['NS1_IP']
    ns2_ips = values['NS2_IP']
    key_zone_m = {'key': {
        'name': name,
        'algorithm': 'hmac-md5',
        'secret': secret},
        'zone': {
        'name': name,
        'zonefile': paths['master'] + name,
        'notify': [(ns2_ips[0], name), (ns2_ips[1], name)],
        'provide-xfr': [(ns2_ips[0], name), (ns2_ips[1], name)]}}

    key_zone_s = {'key': {
        'name': name,
        'algorithm': 'hmac-md5',
        'secret': secret},
        'zone': {
        'name': name,
        'zonefile': paths['slave'] + name,
        'allow-notify': [(ns1_ips[0], name), (ns1_ips[1], name)],
        'request-xfr': [('AXFR ' + ns1_ips[0], name),
                        ('AXFR ' + ns1_ips[1], name)]}}

    master = []
    for i in 'key', 'zone':
        master.append('%s:' % i)
        for j in key_zone_m[i].keys():
            if j == 'provide-xfr' or j == 'notify':
                for k in key_zone_m[i][j]:
                    #master.append('    %s:    %s    %s' % (j, k[0], k[1]))
                    line = '    ' + j + ':    ' + k[0] + '    ' + k[1]
                    master.append(line)
            else:
                if j == 'algorithm':
                    line = '    ' + j + ':    ' + key_zone_m[i][j]

                    master.append(line)
                else:
                    line = '    ' + j + ':    ' + '"' + key_zone_m[i][j] + '"'
                    master.append(line)
    slave = []
    for i in 'key', 'zone':
        line = i + ':    '
        slave.append(line)
        for j in key_zone_s[i].keys():
            if j == 'request-xfr' or j == 'allow-notify':
                for k in key_zone_s[i][j]:
                    line = '    ' + j + ':    ' + k[0] + '    ' + k[1]
                    slave.append(line)
            else:
                if j == 'algorithm':
                    line = '    ' + j + ':    ' + key_zone_s[i][j]
                    slave.append(line)
                else:
                    line = '    ' + j + ':    ' + '"' + key_zone_s[i][j] + '"'
                    slave.append(line)

    key_data = {'master': master, 'slave': slave}
    return key_data


#Генерация НС записей
def make_zone(values, name):
    zone_data = []
    serial = time.strftime('%Y%m%d%H%M%S')
    ns1 = values['NS1']
    ns2 = values['NS2']
    TTL = ['$TTL 1800 ;minimum ttl', '''
           %s      ;serial
           3600            ;refresh
           9600            ;retry
           180000          ;expire
           600             ;negative ttl
           )''' % serial]

    zone_data.append(TTL[0])
    line = name + '.    ' + 'IN    SOA ' +\
        ns1 + ' hostmaster.' + name + '. (' + TTL[1]
    zone_data.append(line)
    zone_data.append(('    ' * 4 + 'NS' + '    ' + ns1))
    zone_data.append(('    ' * 4 + 'NS' + '    ' + ns2))
    zone_data.append(('    ' * 4 + 'A' + '    ' * 2 + values['A']))
    zone_data.append(('    ' * 3 + 'MX    5 ' + values['MX']))

    #Обработка А записей из конфига зоны:
    sample = '[\d*\.]{4}'
    for i in values.keys():
        if i not in ('NS', 'A', 'MX', 'NS1_IP', 'NS2_IP', 'NS1', 'NS2'):
            result = re.findall(sample, values[i])
            if len(result) > 0:
                zone_data.append((i + '    ' * 2 + 'A' + '    ' * 2 +
                                 values[i]))
    return zone_data


if __name__ == '__main__':
    main()
