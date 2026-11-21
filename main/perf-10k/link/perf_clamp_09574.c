/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09574(unsigned int count)
{
    const unsigned int limit = 169u;
    return count > limit ? limit : count;
}
