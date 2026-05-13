using Microsoft.AspNetCore.Mvc;
using Energy_Truth.Shared; // Zorg dat dit overeenkomt met je namespace

[ApiController]
[Route("api/[controller]")]
public class ProductenController : ControllerBase
{
    [HttpGet]
    public List<Test> Get()
    {
        return new List<Test>
        {
            new Test { Naam = "Laptop", Prijs = 999.99m },
            new Test { Naam = "Muis", Prijs = 25.50m }
        };
    }
}
