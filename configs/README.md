# Configs

Los INI de ejemplo son el contrato de cada paso. Los valores de producción
viven fuera de git (copiar a `configs/` local o montar en el contenedor).

`*.ini` en la raíz de `configs/` está en `.gitignore`. Solo se versionan
los de `configs/example/`.

Cuando se transfiera cada módulo, estos archivos se alinean con el parser
real. Hoy son placeholders.
