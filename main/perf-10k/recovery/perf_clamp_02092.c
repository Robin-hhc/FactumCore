/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02092(unsigned int count)
{
    const unsigned int limit = 214u;
    return count > limit ? limit : count;
}
