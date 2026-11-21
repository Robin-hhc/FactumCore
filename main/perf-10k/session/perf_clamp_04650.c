/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04650(unsigned int count)
{
    const unsigned int limit = 125u;
    return count > limit ? limit : count;
}
