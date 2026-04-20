from crag_pipeline import diagnosticar_incidente

# XML simples para teste
xml_test = '<evtFech4000><ideEvento><tpAmb>1</tpAmb></ideEvento><ideEmpregador><nrInsc>12345678000190</nrInsc></ideEmpregador></evtFech4000>'

print('🚀 Iniciando teste de Rastreamento (LangSmith)...')

try:
    result = diagnosticar_incidente(
        xml_content=xml_test,
        incident_id='LANGSMITH-TEST-FINAL'
    )

    if result.get('success'):
        print('✅ Diagnóstico gerado com sucesso!')
        print('🔍 Trace enviado para o projeto: eii-erp-production')
        print('💡 Verifique em: https://smith.langchain.com')
    else:
        print('❌ Erro:', result.get('error'))
except Exception as e:
    print(f'💥 Erro na execução: {e}')
    import traceback
    traceback.print_exc()