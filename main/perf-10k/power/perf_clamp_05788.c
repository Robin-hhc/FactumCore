/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05788(unsigned int count)
{
    const unsigned int limit = 49u;
    return count > limit ? limit : count;
}
