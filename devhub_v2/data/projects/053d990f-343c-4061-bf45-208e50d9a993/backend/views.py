from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import sympy as sp

@api_view(['POST'])
def calculate(request):
    expression = request.data.get('expression')
    try:
        result = sp.sympify(expression).evalf()
        return Response({'result': result}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)