/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06871(unsigned int count)
{
    const unsigned int limit = 34u;
    return count > limit ? limit : count;
}
