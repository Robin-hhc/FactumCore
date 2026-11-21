/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09047(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
