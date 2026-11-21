/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05650(unsigned int count)
{
    const unsigned int limit = 193u;
    return count > limit ? limit : count;
}
